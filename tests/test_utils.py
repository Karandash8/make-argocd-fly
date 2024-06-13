import pytest
import textwrap

from make_argocd_fly.utils import resource_parser, multi_resource_parser, generate_filename, merge_dicts

###################
### resource_parser
###################

def test_resource_parser_simple():
  resource_yml = '''\
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_missing_name():
  resource_yml = '''\
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      namespace: monitoring
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', None)

def test_resource_parser_with_comments():
  resource_yml = '''\
    apiVersion: apps/v1
    #kind: DaemonSet
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_leading_comments():
  resource_yml = '''\
    #kind: DaemonSet
    apiVersion: apps/v1
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_comments_and_leading_kind():
  resource_yml = '''\
    kind: Deployment
    #kind: DaemonSet
    apiVersion: apps/v1
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_messed_up_order_metadata_at_the_beginning():
  resource_yml = '''\
    metadata:
      name: grafana
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_messed_up_order_metadata_in_the_middle():
  resource_yml = '''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_messed_up_order_name_extra_spaces():
  resource_yml = '''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
        name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', None)

def test_resource_parser_with_messed_up_order_name_is_not_first():
  resource_yml = '''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      namespace: monitoring
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_messed_up_order_name_is_not_first_with_comment_1():
  resource_yml = '''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      namespace: monitoring
    # comment
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_messed_up_order_name_is_not_first_with_comments_2():
  resource_yml = '''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      namespace: monitoring
     # comment
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_messed_up_order_name_is_not_first_with_comments_3():
  resource_yml = '''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      namespace: monitoring
      # comment
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_messed_up_order_name_is_not_first_with_comments_4():
  resource_yml = '''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      namespace: monitoring
       # comment
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

###################
### multi_resource_parser
###################

def test_multi_resource_parser_with_valid_yaml():
  # Test when valid YAML is provided with multiple resources
  multi_resource_yml = '''\
    kind: Deployment
    metadata:
      name: grafana
    ---
    kind: DaemonSet
    metadata:
      name: prometheus
    '''

  result = list(multi_resource_parser(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('Deployment', 'grafana', 'kind: Deployment\nmetadata:\n  name: grafana'),
      ('DaemonSet', 'prometheus', 'kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_multi_resource_parser_with_valid_yaml_extra_separator_at_the_top():
  # Test when valid YAML is provided with multiple resources
  multi_resource_yml = '''\
    ---
    kind: Deployment
    metadata:
      name: grafana
    ---
    kind: DaemonSet
    metadata:
      name: prometheus
    '''

  result = list(multi_resource_parser(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('Deployment', 'grafana', 'kind: Deployment\nmetadata:\n  name: grafana'),
      ('DaemonSet', 'prometheus', 'kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_multi_resource_parser_with_valid_yaml_extra_separator_at_the_bottom():
  # Test when valid YAML is provided with multiple resources
  multi_resource_yml = '''\
    kind: Deployment
    metadata:
      name: grafana
    ---
    kind: DaemonSet
    metadata:
      name: prometheus
    ---
    '''

  result = list(multi_resource_parser(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('Deployment', 'grafana', 'kind: Deployment\nmetadata:\n  name: grafana'),
      ('DaemonSet', 'prometheus', 'kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_multi_resource_parser_with_valid_yaml_not_an_extra_separator():
  # Test when valid YAML is provided with multiple resources
  multi_resource_yml = '''\
    kind: Deployment
    metadata:
      name: grafana
      comment: "--- This is not an extra separator"
    ---
    kind: DaemonSet
    metadata:
      name: prometheus
    '''

  result = list(multi_resource_parser(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('Deployment', 'grafana', 'kind: Deployment\nmetadata:\n  name: grafana\n  comment: "--- This is not an extra separator"'),
      ('DaemonSet', 'prometheus', 'kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_multi_resource_parser_with_valid_yaml_not_an_extra_separator_2():
  # Test when valid YAML is provided with multiple resources
  multi_resource_yml = '''\
    kind: Deployment
    metadata:
      name: grafana
      comment: |
        This is not an extra separator ----
    ---
    kind: DaemonSet
    metadata:
      name: prometheus
    '''

  result = list(multi_resource_parser(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('Deployment', 'grafana', 'kind: Deployment\nmetadata:\n  name: grafana\n  comment: |\n    This is not an extra separator ----'),
      ('DaemonSet', 'prometheus', 'kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

#####################
### generate_filename
#####################

def test_generate_filename_undefined_resource_kind(tmp_path, caplog):
  with pytest.raises(Exception):
    generate_filename(None, 'key_1')
  assert 'Parameter `resource_kind` is undefined' in caplog.text

  with pytest.raises(Exception):
    generate_filename('', 'key_1')
  assert 'Parameter `resource_kind` is undefined' in caplog.text

def test_generate_filename(tmp_path):
  assert generate_filename('key_1', 'key_2') == 'key_1_key_2.yml'

def test_generate_filename_undefined_resource_name(tmp_path):
  assert generate_filename('key_1', None) == 'key_1.yml'

###############
### merge_dicts
###############

def test_merge_dicts_non_nested():
    # Test merging two dictionaries with non-nested keys
    dict1 = {'a': 1, 'b': 2}
    dict2 = {'b': 3, 'c': 4}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'b': 3, 'c': 4}

def test_merge_dicts_nested():
    # Test merging dictionaries with nested keys
    dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
    dict2 = {'b': {'c': 4, 'e': 5}, 'f': 6}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'b': {'c': 4, 'd': 3, 'e': 5}, 'f': 6}

def test_merge_dicts_empty_left():
    # Test merging dictionaries with an empty dictionary on the left
    dict1 = {}
    dict2 = {'a': 1, 'b': 2}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'b': 2}

def test_merge_dicts_empty_right():
    # Test merging dictionaries with an empty dictionary on the right (should keep the dictionary on the left)
    dict1 = {'a': 1, 'b': 2}
    dict2 = {}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'b': 2}

def test_merge_dicts_both_empty():
    # Test merging two empty dictionaries
    dict1 = {}
    dict2 = {}
    result = merge_dicts(dict1, dict2)
    assert result == {}

def test_merge_dicts_empty_dict_on_right():
    # Test merging dictionaries with an empty dictionary on the right (should make it an empty dictionary on the left)
    dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
    dict2 = {'b': {}, 'f': None, 'g': 7}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'b': {}, 'g': 7}

def test_merge_dicts_none_value_on_right():
    # Test merging dictionaries with a None value on the right (should delete the key on the left)
    dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
    dict2 = {'b': None, 'f': 6}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'f': 6}

def test_merge_dicts_empty_dict_and_none_value():
    # Test merging dictionaries with a mix of empty dictionary and None value (should behave accordingly)
    dict1 = {'a': {}, 'b': None, 'c': 3}
    dict2 = {'a': {'x': 1}, 'b': 2, 'd': {}}
    result = merge_dicts(dict1, dict2)
    assert result == {'c': 3, 'a': {'x': 1}, 'b': 2, 'd': {}}

def test_merge_dicts_nested_dicts():
    # Test merging dictionaries with nested dictionaries
    dict1 = {'a': {'b': {'c': 1, 'd': 2}}, 'e': 3}
    dict2 = {'a': {'b': {'d': 4, 'e': 5}}, 'f': 6}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': {'b': {'c': 1, 'd': 4, 'e': 5}}, 'e': 3, 'f': 6}

def test_merge_dicts_empty_nested_dict_on_right():
    # Test merging dictionaries with an empty nested dictionary on the right (should make it empty on the left)
    dict1 = {'a': {'b': {'c': 1, 'd': 2}}}
    dict2 = {'a': {'b': {}}}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': {'b': {}}}

def test_merge_dicts_three_dicts():
    # Test merging three dictionaries with various corner cases
    dict1 = {'a': 1, 'b': 2, 'c': {'x': 10, 'y': 20}}
    dict2 = {'b': 3, 'c': {'x': 30, 'z': 40}, 'd': 4}
    dict3 = {'c': {'z': 300, 'w': 400}, 'e': 5}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # 'a' and 'd' keys from dict1, 'e' key from dict3, and 'w' key from dict3 should be in the result
    # 'b' key should take the value from dict2, 'c' key should merge values from all dictionaries
    assert result == {'a': 1, 'b': 3, 'c': {'x': 30, 'y': 20, 'z': 300, 'w': 400}, 'd': 4, 'e': 5}

def test_merge_dicts_three_empty_dicts():
    # Test merging three empty dictionaries
    dict1 = {}
    dict2 = {}
    dict3 = {}

    # Merging three empty dictionaries should result in an empty dictionary
    result = merge_dicts(dict1, dict2, dict3)
    assert result == {}

def test_merge_dicts_three_nested_dicts():
    # Test merging three dictionaries with nested dictionaries
    dict1 = {'a': {'x': 1, 'y': {'z': 2}}}
    dict2 = {'a': {'y': {'z': 3, 'w': 4}}}
    dict3 = {'a': {'w': 5, 'u': {'v': 6}}}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # Merged dictionaries should contain all keys and nested dictionaries
    assert result == {'a': {'x': 1, 'y': {'z': 3, 'w': 4}, 'w': 5, 'u': {'v': 6}}}

def test_merge_dicts_three_empty_nested_dict():
    # Test merging three dictionaries with empty nested dictionaries
    dict1 = {'a': {}}
    dict2 = {'a': {'x': 1}}
    dict3 = {'a': {'y': 2, 'z': {}}}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # Merged dictionaries should contain empty nested dictionary
    assert result == {'a': {'x': 1, 'y': 2, 'z': {}}}

def test_merge_dicts_three_dicts_with_none():
    # Test merging three dictionaries with various scenarios involving None values
    dict1 = {'a': 1, 'b': 2, 'c': {'x': 10, 'y': 20}}
    dict2 = {'b': 3, 'c': {'x': None, 'z': 40}, 'd': None}
    dict3 = {'c': {'z': 300, 'w': 400}, 'e': None}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # 'a', 'd', and 'e' keys from dict1, 'd' key from dict2 should be removed
    # 'b' key should take the value from dict2, 'c' key should merge values from all dictionaries
    assert result == {'a': 1, 'b': 3, 'c': {'y': 20, 'z': 300, 'w': 400}}

def test_merge_dicts_three_nested_dicts_with_none():
    # Test merging three dictionaries with nested dictionaries containing None values
    dict1 = {'a': {'x': 1, 'y': {'z': 2, 'w': None}}}
    dict2 = {'a': {'y': {'z': 3, 'w': 4, 'v': None}}}
    dict3 = {'a': {'w': 5, 'u': {'v': 6, 'x': None}}}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # None values should override other values in the merged dictionaries
    assert result == {'a': {'x': 1, 'y': {'z': 3, 'w': 4}, 'w': 5, 'u': {'v': 6}}}

def test_merge_dicts_three_none_values():
    # Test merging three dictionaries with None values
    dict1 = {'a': None, 'b': {'x': None, 'y': 20}}
    dict2 = {'b': None, 'c': None, 'd': 4}
    dict3 = {'c': None, 'e': None}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # All keys with None values should be removed
    assert result == {'d': 4}

def test_merge_dicts_three_dicts_with_empty_nested():
    # Test merging three dictionaries with empty nested dictionaries
    dict1 = {'a': {'b': {}}, 'c': {'d': 1}}
    dict2 = {'a': {'b': {}}, 'c': {'d': 2}}
    dict3 = {'a': {'b': {}}, 'c': {'d': 3}}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # Merged dictionaries should contain empty nested dictionaries
    assert result == {'a': {'b': {}}, 'c': {'d': 3}}

def test_merge_dicts_non_nested_and_nested_keys_with_none():
    # Test merging dictionaries with non-nested and nested keys, and None values
    dict1 = {'a': 1, 'b': {'c': 2, 'd': 3, 'e': None}}
    dict2 = {'b': {'c': 4, 'e': 5, 'f': None}, 'g': 6}
    dict3 = {'h': None, 'i': {'j': 7, 'k': None}}
    result = merge_dicts(dict1, dict2, dict3)
    assert result == {'a': 1, 'b': {'c': 4, 'd': 3, 'e': 5}, 'g': 6, 'i': {'j': 7}}

def test_merge_dicts_deeply_nested_keys():
    # Test merging dictionaries with deeply nested keys
    dict1 = {'a': {'b': {'c': {'d': {'e': 1}}}}}
    dict2 = {'a': {'b': {'c': {'d': {'f': 2}}}}}
    dict3 = {'a': {'b': {'c': {'d': {'g': 3}}}}}
    result = merge_dicts(dict1, dict2, dict3)
    assert result == {'a': {'b': {'c': {'d': {'e': 1, 'f': 2, 'g': 3}}}}}

def test_merge_dicts_empty_nested_and_none_values():
    # Test merging dictionaries with empty nested dictionaries and None values
    dict1 = {'a': {'b': {}}, 'c': {'d': 1, 'e': None}}
    dict2 = {'a': {'b': {'f': None}}, 'c': {'d': 2, 'e': 3}}
    dict3 = {'a': {'b': {'g': None}}, 'c': {'d': None, 'h': 4}}
    result = merge_dicts(dict1, dict2, dict3)
    assert result == {'a': {'b': {}}, 'c': {'e': 3, 'h': 4}}
