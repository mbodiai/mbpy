import pytest
from mbpy.utils.parse_utils import parse_args_from_string

def test_parse_args_from_string_json():
  arg_string = '{"key1": "value1", "key2": "value2"}'
  expected = {"key1": "value1", "key2": "value2"}
  assert parse_args_from_string(arg_string) == expected

def test_parse_args_from_string_ros2():
  arg_string = "key1:=value1 key2:=value2"
  expected = {"key1": "value1", "key2": "value2"}
  assert parse_args_from_string(arg_string) == expected

def test_parse_args_from_string_key_value():
  arg_string = "key1=value1 key2=value2"
  expected = {"key1": "value1", "key2": "value2"}
  assert parse_args_from_string(arg_string) == expected

def test_parse_args_from_string_command_line():
  arg_string = "--key1 value1 --key2 value2"
  expected = {"key1": "value1", "key2": "value2"}
  assert parse_args_from_string(arg_string) == expected

def test_parse_args_from_string_json_file():
  arg_string = "args.json"
  file_contents = '{"key1": "value1", "key2": "value2"}'
  expected = {"key1": "value1", "key2": "value2"}
  assert parse_args_from_string(arg_string, file_contents) == expected

def test_parse_args_from_string_yaml_file():
  arg_string = "args.yaml"
  file_contents = "key1: value1\nkey2: value2"
  expected = {"key1": "value1", "key2": "value2"}
  assert parse_args_from_string(arg_string, file_contents) == expected

def test_parse_args_from_string_ros_file():
  arg_string = "args.ros"
  file_contents = "key1:=value1 key2:=value2"
  expected = {"key1": "value1", "key2": "value2"}
  assert parse_args_from_string(arg_string, file_contents) == expected

def test_parse_args_from_string_yaml_string():
  arg_string = "key1: value1\nkey2: value2"
  expected = {"key1": "value1", "key2": "value2"}
  assert parse_args_from_string(arg_string) == expected

def test_parse_args_from_string_unsupported_format():
  arg_string = "unsupported format"
  with pytest.raises(ValueError, match="Unsupported input format"):
    parse_args_from_string(arg_string)