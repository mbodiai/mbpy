import pytest
import requests
from mbpy.mpip import (
    get_latest_version,
    base_name,
    modify_dependencies,
    is_group,
    process_dependencies,
    search_package,
    find_and_sort,
    format_dependency,
)


def test_get_latest_version():
    assert get_latest_version("pytest") is not None
    # Test with a non-existent package
    assert get_latest_version("non_existent_package_12345") is None


def test_base_name():
    assert base_name("package") == "package"
    assert base_name("package[extra]") == "package"
    assert base_name("package==1.0.0") == "package"


def test_modify_dependencies():
    dependencies = ["package1==1.0.0", "package2==2.0.0"]

    # Test install action
    result = modify_dependencies(dependencies, "package3==3.0.0", "install")
    assert "package3==3.0.0" in result
    assert len(result) == 3

    # Test uninstall action
    result = modify_dependencies(dependencies, "package1==1.0.0", "uninstall")
    assert "package1==1.0.0" not in result
    assert len(result) == 1


def test_is_group():
    assert is_group("[group]") is True
    assert is_group("not_a_group") is False
    assert is_group('[group with "quotes"]') is False

@pytest.fixture
def test_pyproject():
    return """[tool.hatch.envs.default]
python = "3.12"
path = ".mrender/envs/mrender"
dependencies = [
    "pytest",
    "pytest-mock",
    "pytest-asyncio",
]
[tool.hatch.envs.default.env-vars]"""

def test_process_dependencies_group(test_pyproject):
    output_lines = []
    process_dependencies(test_pyproject.replace("\n", ""), output_lines)
def test_process_dependencies_quotes_inside_strings():
    output_lines = []
    process_dependencies(' "dep",', output_lines)
    assert output_lines == ['  "dep"']

    output_lines = []
    process_dependencies(' "dep", "dep2",', output_lines)
    assert output_lines == ['  "dep"', '  "dep2"']

    output_lines = []
    process_dependencies(' "dep", "dep2", "dep3",', output_lines)
    assert output_lines == ['  "dep"', '  "dep2"', '  "dep3"']

    output_lines = []
    process_dependencies(' "dep", "dep2", "dep3", "dep4",', output_lines)
    assert output_lines == ['  "dep"', '  "dep2"', '  "dep3"', '  "dep4"']

    output_lines = []
    process_dependencies(' "dep", "dep2", "dep3", "dep4", "dep5",', output_lines)
    assert output_lines == ['  "dep"', '  "dep2"', '  "dep3"', '  "dep4"', '  "dep5"']

    output_lines = []
    process_dependencies(' "dep", "dep2", "dep3", "dep4", "dep5", "dep6",', output_lines)
    assert output_lines == ['  "dep"', '  "dep2"', '  "dep3"', '  "dep4"', '  "dep5"', '  "dep6"']


def test_process_dependencies_group_with_extras(test_pyproject):
    output_lines = []
    dependencies = test_pyproject.split('dependencies = [')[1].split(']')[0].strip()
    process_dependencies(dependencies, output_lines)
    assert output_lines == [
        '  "pytest"',
        '  "pytest-mock"',
        '  "pytest-asyncio"',
    ]


def test_process_dependencies_quotes_inside_strings_with_extras():
    output_lines = []
    process_dependencies('dep[extra],', output_lines)
    assert output_lines == ['  "dep[extra]"']

    output_lines = []
    process_dependencies('dep[extra1,extra2],', output_lines)
    assert output_lines == ['  "dep[extra1, extra2]"']

    output_lines = []
    process_dependencies('dep[extra1,extra2], dep2[extra3],', output_lines)
    assert output_lines == ['  "dep[extra1, extra2]"', '  "dep2[extra3]"']

    output_lines = []
    process_dependencies('dep[extra1,extra2], dep2[extra3], dep3[extra4],', output_lines)
    assert output_lines == ['  "dep[extra1, extra2]"', '  "dep2[extra3]"', '  "dep3[extra4]"']

    output_lines = []
    process_dependencies('dep[extra1,extra2], dep2[extra3], dep3[extra4], dep4[extra5],', output_lines)
    assert output_lines == ['  "dep[extra1, extra2]"', '  "dep2[extra3]"', '  "dep3[extra4]"', '  "dep4[extra5]"']

    output_lines = []
    process_dependencies('dep[extra1,extra2], dep2[extra3], dep3[extra4], dep4[extra5], dep5[extra6],', output_lines)
    assert output_lines == ['  "dep[extra1, extra2]"', '  "dep2[extra3]"', '  "dep3[extra4]"', '  "dep4[extra5]"', '  "dep5[extra6]"']

    output_lines = []
    process_dependencies('dep[extra1,extra2], dep2[extra3], dep3[extra4], dep4[extra5], dep5[extra6], dep6[extra7],', output_lines)
    assert output_lines == ['  "dep[extra1, extra2]"', '  "dep2[extra3]"', '  "dep3[extra4]"', '  "dep4[extra5]"', '  "dep5[extra6]"', '  "dep6[extra7]"']

def test_process_dependencies_remove_extra_quotes():
    output_lines = []
    process_dependencies('dep1, dep2', output_lines)
    assert output_lines == ['  "dep1"', '  "dep2"']

def test_process_dependencies_hard_to_format():
    output_lines = []
    process_dependencies('[dep[extra1,extra2], dep99[extra100],]', output_lines)
    assert output_lines == [
        '[',
        '  "dep[extra1, extra2]"',
        '  "dep99[extra100]"',
        ']',
    ]

def test_process_dependencies_trailing_comma():
    output_lines = []
    process_dependencies("dep1, dep2,", output_lines)
    assert output_lines == ['  "dep1"', '  "dep2"']

def test_process_dependencies_single():
    result = process_dependencies("requests")
    assert result == ['  "requests"']

def test_process_dependencies_multiple():
    result = process_dependencies("requests, flask")
    assert result == ['  "requests"', '  "flask"']

def test_process_dependencies_with_extras():
    result = process_dependencies("requests[security, socks]")
    assert result == ['  "requests[security,  socks]"']

def test_process_dependencies_with_version():
    result = process_dependencies("requests==2.25.1")
    assert result == ['  "requests==2.25.1"']

def test_process_dependencies_complex():
    result = process_dependencies("[requests[security,socks]==2.25.1, flask>=1.0]")
    assert result == ['[', '  "requests[security, socks]==2.25.1"', '  "flask>=1.0"', ']']

def test_process_dependencies_with_brackets():
    result = process_dependencies("[requests, flask]")
    assert result == ['[', '  "requests"', '  "flask"', ']']

def test_format_dependency():
    assert format_dependency("requests") == "  \"requests\""
    assert format_dependency("\"requests[security,socks]\"") == "  \"requests[security, socks]\""
    assert format_dependency("requests==2.25.1") == "  \"requests==2.25.1\""
    assert format_dependency("requests[security,socks]==2.25.1") == "  \"requests[security, socks]==2.25.1\""
    assert format_dependency("\"package[extra1,extra2]==1.0.0\"") == "  \"package[extra1, extra2]==1.0.0\""
    assert format_dependency("package[extra1,extra2]>=1.0.0,<2.0.0") == "  \"package[extra1, extra2]>=1.0.0,<2.0.0\""

# @pytest.mark.parametrize("package_name, mock_response, expected_result", [
#     ("pytest", {"info": {"version": "1.2.3"}}, "1.2.3"),
#     ("non_existent_package_12345", None, None),
# ])
# def test_get_latest_version(mocker, package_name, mock_response, expected_result):
#     mock_get = mocker.patch('requests.get')
#     mock_get.return_value.json.return_value = mock_response
#     mock_get.return_value.raise_for_status = mocker.Mock()

#     result = get_latest_version(package_name)
#     assert result == expected_result

#     if mock_response is None:
#         mock_get.side_effect = requests.RequestException
