import base64
import dataclasses
import gzip
import hashlib
import importlib
from pathlib import Path
import re
import sys
from typing import (
    IO,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
)
import xml.etree.ElementTree as ET

from defusedxml.ElementTree import parse as parse_xml
import docutils.core

NETLIFY_CHAR_BLACKLIST = frozenset('":<>|*?\r\n#')
"""Characters not allowed in output filenames"""


@dataclasses.dataclass
class CaseResult:
    module_name: str
    class_name: str
    test_name: str
    job: str
    success: bool
    skipped: bool
    system_out: Optional[str]
    details: Optional[str] = None
    type: Optional[str] = None
    message: Optional[str] = None

    def output_filename(self) -> str:
        test_name = self.test_name
        if len(test_name) > 50 or set(test_name) & NETLIFY_CHAR_BLACKLIST:
            # File name too long or otherwise invalid. This should be good enough:
            m = re.match(r"(?P<function_name>\w+?)\[(?P<params>.+)\]", test_name)
            assert m, "File name is too long but has no parameter."
            test_name = f'{m.group("function_name")}[{md5sum(m.group("params"))}]'
        return f"{self.job}_{self.module_name}.{self.class_name}.{test_name}.txt"


TK = TypeVar("TK")
TV = TypeVar("TV")


def md5sum(text: str) -> str:
    return base64.urlsafe_b64encode(hashlib.md5(text.encode()).digest()).decode()


def group_by(list_: Iterable[TV], key: Callable[[TV], TK]) -> Dict[TK, List[TV]]:
    groups: Dict[TK, List[TV]] = {}
    for value in list_:
        groups.setdefault(key(value), []).append(value)

    return groups


def iter_job_results(job_file_name: Path, job: ET.ElementTree) -> Iterator[CaseResult]:
    (suite,) = job.getroot()
    for case in suite:
        if "name" not in case.attrib:
            continue

        success = True
        skipped = False
        details = None
        system_out = None
        extra: Dict[str, str] = {}
        for child in case:
            if child.tag == "skipped":
                success = True
                skipped = True
                details = None
                extra = child.attrib
            elif child.tag in ("failure", "error"):
                success = False
                skipped = False
                details = child.text
                extra = child.attrib
            elif child.tag == "system-out":
                assert (
                    system_out is None
                    # for some reason, skipped tests have two system-out;
                    # and the second one contains test teardown
                    or child.text.startswith(system_out.rstrip())
                ), ("Duplicate system-out tag", repr(system_out), repr(child.text))
                system_out = child.text
            else:
                assert False, child

        (module_name, class_name) = case.attrib["classname"].rsplit(".", 1)
        m = re.match(
            r"(.*/)?pytest[ -]results[ _](?P<name>.*)"
            r"[ _][(]?(stable|release|devel|devel_release)[)]?/pytest.xml(.gz)?",
            str(job_file_name),
        )
        assert m, job_file_name
        yield CaseResult(
            module_name=module_name,
            class_name=class_name,
            test_name=case.attrib["name"],
            job=m.group("name"),
            success=success,
            skipped=skipped,
            details=details,
            system_out=system_out,
            **extra,
        )


def rst_to_element(s: str) -> ET.Element:
    html = docutils.core.publish_parts(s, writer_name="xhtml")["html_body"]
    htmltree = ET.fromstring(html)
    return htmltree


def append_docstring(element: ET.Element, obj: object) -> None:
    if obj.__doc__ is None:
        return

    element.append(rst_to_element(obj.__doc__))


def build_job_html(job: str, results: List[CaseResult]) -> ET.Element:
    jobs = sorted({result.job for result in results})
    root = ET.Element("html")
    head = ET.SubElement(root, "head")
    ET.SubElement(head, "title").text = job
    ET.SubElement(head, "link", rel="stylesheet", type="text/css", href="./style.css")

    body = ET.SubElement(root, "body")

    ET.SubElement(body, "h1").text = job

    table = build_test_table(jobs, results)
    table.set("class", "job-results test-matrix")
    body.append(table)

    return root


def build_module_html(
    jobs: List[str], results: List[CaseResult], module_name: str
) -> ET.Element:
    module = importlib.import_module(module_name)

    root = ET.Element("html")
    head = ET.SubElement(root, "head")
    ET.SubElement(head, "title").text = module_name
    ET.SubElement(head, "link", rel="stylesheet", type="text/css", href="./style.css")

    body = ET.SubElement(root, "body")

    ET.SubElement(body, "h1").text = module_name

    append_docstring(body, module)

    table = build_test_table(jobs, results)
    table.set("class", "module-results test-matrix")
    body.append(table)

    return root


def build_test_table(jobs: List[str], results: List[CaseResult]) -> ET.Element:
    multiple_modules = len({r.module_name for r in results}) > 1
    results_by_module_and_class = group_by(
        results, lambda r: (r.module_name, r.class_name)
    )

    table = ET.Element("table")

    job_row = ET.Element("tr")
    ET.SubElement(job_row, "th")  # column of case name
    for job in jobs:
        cell = ET.SubElement(job_row, "th")
        ET.SubElement(ET.SubElement(cell, "div"), "span").text = job
        cell.set("class", "job-name")

    for (module_name, class_name), class_results in sorted(
        results_by_module_and_class.items()
    ):
        if multiple_modules:
            # if the page shows classes from various modules, use the fully-qualified
            # name in order to disambiguate and be clearer (eg. show
            # "irctest.server_tests.extended_join.MetadataTestCase" instead of just
            # "MetadataTestCase" which looks like it's about IRCv3's METADATA spec.
            qualified_class_name = f"{module_name}.{class_name}"
        else:
            # otherwise, it's not needed, so let's not display it
            qualified_class_name = class_name

        module = importlib.import_module(module_name)

        # Header row: class name
        header_row = ET.SubElement(table, "tr")
        th = ET.SubElement(header_row, "th", colspan=str(len(jobs) + 1))
        row_anchor = f"{qualified_class_name}"
        section_header = ET.SubElement(
            ET.SubElement(th, "h2"),
            "a",
            href=f"#{row_anchor}",
            id=row_anchor,
        )
        section_header.text = qualified_class_name
        append_docstring(th, getattr(module, class_name))

        # Header row: one column for each implementation
        table.append(job_row)

        # One row for each test:
        results_by_test = group_by(class_results, key=lambda r: r.test_name)
        for test_name, test_results in sorted(results_by_test.items()):
            row_anchor = f"{qualified_class_name}.{test_name}"
            if len(row_anchor) >= 50:
                # Too long; give up on generating readable URL
                # TODO: only hash test parameter
                row_anchor = md5sum(row_anchor)

            row = ET.SubElement(table, "tr", id=row_anchor)

            cell = ET.SubElement(row, "th")
            cell.set("class", "test-name")
            cell_link = ET.SubElement(cell, "a", href=f"#{row_anchor}")
            cell_link.text = test_name

            results_by_job = group_by(test_results, key=lambda r: r.job)
            for job_name in jobs:
                cell = ET.SubElement(row, "td")
                try:
                    (result,) = results_by_job[job_name]
                except KeyError:
                    cell.set("class", "deselected")
                    cell.text = "d"
                    continue

                text: Optional[str]

                if result.skipped:
                    cell.set("class", "skipped")
                    if result.type == "pytest.skip":
                        text = "s"
                    elif result.type == "pytest.xfail":
                        text = "X"
                        cell.set("class", "expected-failure")
                    else:
                        text = result.type
                elif result.success:
                    cell.set("class", "success")
                    if result.type:
                        # dead code?
                        text = result.type
                    else:
                        text = "."
                else:
                    cell.set("class", "failure")
                    if result.type:
                        # dead code?
                        text = result.type
                    else:
                        text = "f"

                if result.system_out:
                    # There is a log file; link to it.
                    a = ET.SubElement(cell, "a", href=f"./{result.output_filename()}")
                    a.text = text or "?"
                else:
                    cell.text = text or "?"
                if result.message:
                    cell.set("title", result.message)

    return table


def write_html_pages(
    output_dir: Path, results: List[CaseResult]
) -> List[Tuple[str, str, str]]:
    """Returns the list of (module_name, file_name)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results_by_module = group_by(results, lambda r: r.module_name)

    # used as columns
    jobs = list(sorted({r.job for r in results}))

    job_categories = {}
    for job in jobs:
        is_client = any(
            "client_tests" in result.module_name and result.job == job
            for result in results
        )
        is_server = any(
            "server_tests" in result.module_name and result.job == job
            for result in results
        )
        assert is_client != is_server, (job, is_client, is_server)
        if job.endswith(("-atheme", "-anope", "-dlk")):
            assert is_server
            job_categories[job] = "server-with-services"
        elif is_server:
            job_categories[job] = "server"  # with or without services
        else:
            assert is_client
            job_categories[job] = "client"

    pages = []

    for module_name, module_results in sorted(results_by_module.items()):
        # Filter out client jobs if this is a server test module, and vice versa
        module_categories = {
            job_categories[result.job]
            for result in results
            if result.module_name == module_name and not result.skipped
        }

        module_jobs = [job for job in jobs if job_categories[job] in module_categories]

        root = build_module_html(module_jobs, module_results, module_name)
        file_name = f"{module_name}.xhtml"
        write_xml_file(output_dir / file_name, root)
        pages.append(("module", module_name, file_name))

    for category in ("server", "client"):
        for job in [job for job in job_categories if job_categories[job] == category]:
            job_results = [
                result
                for result in results
                if result.job == job or result.job.startswith(job + "-")
            ]
            root = build_job_html(job, job_results)
            file_name = f"{job}.xhtml"
            write_xml_file(output_dir / file_name, root)
            pages.append(("job", job, file_name))

    return pages


def write_test_outputs(output_dir: Path, results: List[CaseResult]) -> None:
    """Writes stdout files of each test."""
    for result in results:
        if result.system_out is None:
            continue
        output_file = output_dir / result.output_filename()
        with output_file.open("wt") as fd:
            fd.write(result.system_out)


def write_html_index(output_dir: Path, pages: List[Tuple[str, str, str]]) -> None:
    root = ET.Element("html")
    head = ET.SubElement(root, "head")
    ET.SubElement(head, "title").text = "irctest dashboard"
    ET.SubElement(head, "link", rel="stylesheet", type="text/css", href="./style.css")

    body = ET.SubElement(root, "body")

    ET.SubElement(body, "h1").text = "irctest dashboard"

    module_pages = []
    job_pages = []
    for page_type, title, file_name in sorted(pages):
        if page_type == "module":
            module_pages.append((title, file_name))
        elif page_type == "job":
            job_pages.append((title, file_name))
        else:
            assert False, page_type

    ET.SubElement(body, "h2").text = "Tests by command/specification"

    dl = ET.SubElement(body, "dl")
    dl.set("class", "module-index")

    for module_name, file_name in sorted(module_pages):
        module = importlib.import_module(module_name)

        link = ET.SubElement(ET.SubElement(dl, "dt"), "a", href=f"./{file_name}")
        link.text = module_name
        append_docstring(ET.SubElement(dl, "dd"), module)

    ET.SubElement(body, "h2").text = "Tests by implementation"

    ul = ET.SubElement(body, "ul")
    ul.set("class", "job-index")

    for job, file_name in sorted(job_pages):
        link = ET.SubElement(ET.SubElement(ul, "li"), "a", href=f"./{file_name}")
        link.text = job

    write_xml_file(output_dir / "index.xhtml", root)


def write_assets(output_dir: Path) -> None:
    css_path = output_dir / "style.css"
    source_css_path = Path(__file__).parent / "style.css"
    with css_path.open("wt") as fd:
        with source_css_path.open() as source_fd:
            fd.write(source_fd.read())


def write_xml_file(filename: Path, root: ET.Element) -> None:
    # Hacky: ET expects the namespace to be present in every tag we create instead;
    # but it would be excessively verbose.
    root.set("xmlns", "http://www.w3.org/1999/xhtml")

    # Serialize
    s = ET.tostring(root)

    with filename.open("wb") as fd:
        fd.write(s)


def parse_xml_file(filename: Path) -> ET.ElementTree:
    fd: IO
    if filename.suffix == ".gz":
        with gzip.open(filename, "rb") as fd:  # type: ignore
            return parse_xml(fd)  # type: ignore
    else:
        with open(filename) as fd:
            return parse_xml(fd)  # type: ignore


def main(output_path: Path, filenames: List[Path]) -> int:
    results = [
        result
        for filename in filenames
        for result in iter_job_results(filename, parse_xml_file(filename))
    ]

    pages = write_html_pages(output_path, results)

    write_html_index(output_path, pages)
    write_test_outputs(output_path, results)
    write_assets(output_path)

    return 0


if __name__ == "__main__":
    (_, output_path, *filenames) = sys.argv
    exit(main(Path(output_path), list(map(Path, filenames))))
