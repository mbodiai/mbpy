import pytest
from mbpy.docparser import DocumentProcessor, Classification, OutputFormat
import json

@pytest.fixture
def processor():
  return DocumentProcessor()

def test_classify_line(processor):
  assert processor.classify_line("# Header") == "header"
  assert processor.classify_line(".documentation line") == "documentation"
  assert processor.classify_line("UPPERCASE") == "capital_alpha"
  assert processor.classify_line("lowercase") == "lower_alpha"
  assert processor.classify_line("12345") == "numeric"
  assert processor.classify_line("- bullet point") == "bullet"
  assert processor.classify_line("* another bullet") == "bullet"
  assert processor.classify_line("@unknown") == "other"

def test_process_document(processor):
  text = """
# Header
.documentation line
UPPERCASE line
lowercase line
- bullet point
* another bullet
12345
"""
  classifications = processor.process_document(text)
  assert len(classifications) == 7
  assert classifications[0].outer_class == "header"
  assert classifications[1].outer_class == "documentation"
  assert classifications[2].outer_class == "capital_alpha"
  assert classifications[3].outer_class == "lower_alpha"
  assert classifications[4].outer_class == "bullet"
  assert classifications[5].outer_class == "bullet"
  assert classifications[6].outer_class == "numeric"

def test_group_by_outer_class(processor):
  classifications = [
    Classification(line="# Header", line_number=1, outer_class="header"),
    Classification(line=".doc", line_number=2, outer_class="documentation"),
    Classification(line="UPPER", line_number=3, outer_class="capital_alpha"),
    Classification(line="lower", line_number=4, outer_class="lower_alpha"),
  ]
  grouped = processor.group_by_outer_class(classifications)
  assert len(grouped) == 4
  assert grouped["header"] == [classifications[0]]
  assert grouped["documentation"] == [classifications[1]]
  assert grouped["capital_alpha"] == [classifications[2]]
  assert grouped["lower_alpha"] == [classifications[3]]

def test_format_output_markdown(processor):
  classifications = [
    Classification(line="# Header", line_number=1, outer_class="header"),
    Classification(line=".doc", line_number=2, outer_class="documentation"),
  ]
  markdown = processor.format_output(classifications, OutputFormat.MARKDOWN)
  assert "<details>" in markdown
  assert "<summary># Header (Line 1)</summary>" in markdown
  assert "<summary>.doc (Line 2)</summary>" in markdown
  assert "</details>" in markdown

def test_format_output_json(processor):
  classifications = [
    Classification(line="# Header", line_number=1, outer_class="header"),
    Classification(line=".doc", line_number=2, outer_class="documentation"),
  ]
  json_output = processor.format_output(classifications, OutputFormat.JSON)
  data = json.loads(json_output)
  assert len(data) == 2
  assert data[0]["line"] == "# Header"
  assert data[0]["line_number"] == 1
  assert data[0]["outer_class"] == "header"
  assert data[1]["line"] == ".doc"
  assert data[1]["line_number"] == 2
  assert data[1]["outer_class"] == "documentation"

def test_process_empty_document(processor):
  text = ""
  classifications = processor.process_document(text)
  assert classifications == []

def test_process_document_with_subclassifications(processor):
  text = """
# Header
  . Sub doc
    UPPER Sub UPPER
  lower Sub lower
"""
  classifications = processor.process_document(text)
  assert len(classifications) == 1
  header = classifications[0]
  assert header.line == "# Header"
  assert len(header.sub_classifications) == 2
  sub_doc = header.sub_classifications[0]
  assert sub_doc.line.strip() == ". Sub doc"
  assert len(sub_doc.sub_classifications) == 1
  sub_upper = sub_doc.sub_classifications[0]
  assert sub_upper.line.strip() == "UPPER Sub UPPER"
  sub_lower = header.sub_classifications[1]
  assert sub_lower.line.strip() == "lower Sub lower"
def test_deep_nested_classifications(processor):
    text = """
  # Root Header
    . First Level
    UPPER Deeper
      lower Even Deeper
      1234 Deepest
    - Another First Level
    * Another Deeper
      # A Very Deep header
  """
    classifications = processor.process_document(text)
    assert len(classifications) == 2

    root_header = classifications[0]
    assert root_header.line.strip() == "# Root Header"
    assert len(root_header.sub_classifications) == 2

    first_level = root_header.sub_classifications[0]
    assert first_level.line.strip() == ". First Level"
    assert len(first_level.sub_classifications) == 1

    deeper = first_level.sub_classifications[0]
    assert deeper.line.strip() == "UPPER Deeper"
    assert len(deeper.sub_classifications) == 1

    even_deeper = deeper.sub_classifications[0]
    assert even_deeper.line.strip() == "lower Even Deeper"
    assert len(even_deeper.sub_classifications) == 1

    deepest = even_deeper.sub_classifications[0]
    assert deepest.line.strip() == "1234 Deepest"
    assert deepest.sub_classifications == []

    another_first = root_header.sub_classifications[1]
    assert another_first.line.strip() == "- Another First Level"
    assert len(another_first.sub_classifications) == 1

    another_deeper = another_first.sub_classifications[0]
    assert another_deeper.line.strip() == "* Another Deeper"
    assert len(another_deeper.sub_classifications) == 1

    very_deep = another_deeper.sub_classifications[0]
    assert very_deep.line.strip() == "# A Very Deep header"
    assert very_deep.sub_classifications == []

def test_mixed_indentations(processor):
    text = """
  # Top
    . Indented
    UPPER Not Indented
    . Another Indented
  """
    classifications = processor.process_document(text)
    assert len(classifications) == 2
    top_class = classifications[0]
    assert top_class.line.strip() == "# Top"
    assert len(top_class.sub_classifications) == 1
    indented = top_class.sub_classifications[0]
    assert indented.line.strip() == ". Indented"

    not_indented = classifications[1]
    assert not_indented.line.strip() == "UPPER Not Indented"
    assert len(not_indented.sub_classifications) == 1
    another_indented = not_indented.sub_classifications[0]
    assert another_indented.line.strip() == ". Another Indented"


if __name__ == "__main__":
  pytest.main(['-v', __file__])