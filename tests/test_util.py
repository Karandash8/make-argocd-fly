import logging
import pytest
import textwrap

from make_argocd_fly.util import (extract_single_resource, merge_dicts_with_overrides, merge_dicts_without_duplicates, VarsResolver,
                                  get_module_name, get_package_name, build_path, extract_undefined_variable)
from make_argocd_fly.exception import InternalError, UnknownJinja2Error, MergeError, ConfigFileError


###################
### extract_single_resource
###################

def test_extract_single_resource_with_valid_yaml():
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

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
    ('kind: Deployment\nmetadata:\n  name: grafana'),
    ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_valid_yaml_extra_separator_at_the_top():
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

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
    ('kind: Deployment\nmetadata:\n  name: grafana'),
    ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_valid_yaml_extra_separator_at_the_bottom():
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

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
    ('kind: Deployment\nmetadata:\n  name: grafana'),
    ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_single_yaml_extra_separator_at_the_bottom():
  multi_resource_yml = '''\
    kind: DaemonSet
    metadata:
      name: prometheus
    ---
    '''

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
    ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_single_yaml_extra_separator_at_the_bottom_without_new_line():
  multi_resource_yml = '''\
    kind: DaemonSet
    metadata:
      name: prometheus
    ---'''

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
    ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_valid_yaml_not_an_extra_separator():
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

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
    ('kind: Deployment\nmetadata:\n  name: grafana\n  comment: "--- This is not an extra separator"'),
    ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_valid_yaml_not_an_extra_separator_2():
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

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
    ('kind: Deployment\nmetadata:\n  name: grafana\n  comment: |\n    This is not an extra separator ----'),
    ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

###############
### merge_dicts_without_duplicates
###############

def test_merge_dicts_without_duplicates__two_empty():
  dict1 = {}
  dict2 = {}

  result = merge_dicts_without_duplicates(dict1, dict2)
  assert result == {}

def test_merge_dicts_without_duplicates__first_empty():
  dict1 = {}
  dict2 = {'a': 1, 'b': 2}

  result = merge_dicts_without_duplicates(dict1, dict2)
  assert result == {'a': 1, 'b': 2}

def test_merge_dicts_without_duplicates__second_empty():
  dict1 = {'a': 1, 'b': 2}
  dict2 = {}

  result = merge_dicts_without_duplicates(dict1, dict2)
  assert result == {'a': 1, 'b': 2}

def test_merge_dicts_without_duplicates__simple_keys():
  dict1 = {'a': 1, 'b': 2}
  dict2 = {'c': 4}

  result = merge_dicts_without_duplicates(dict1, dict2)
  assert result == {'a': 1, 'b': 2, 'c': 4}

def test_merge_dicts_without_duplicates__simple_keys_with_duplicate(caplog):
  dict1 = {'a': 1, 'b': 2}
  dict2 = {'b': 3, 'c': 4}

  with pytest.raises(MergeError):
    merge_dicts_without_duplicates(dict1, dict2)
  assert 'Duplicate key \'b\'' in caplog.text

def test_merge_dicts_without_duplicates__nested_keys():
  dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
  dict2 = {'b': {'e': 4, 'f': 5}, 'f': 6}

  result = merge_dicts_without_duplicates(dict1, dict2)
  assert result == {'a': 1, 'b': {'c': 2, 'd': 3, 'e': 4, 'f': 5}, 'f': 6}

def test_merge_dicts_without_duplicates__nested_keys_with_duplicate(caplog):
  dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
  dict2 = {'b': {'c': 4, 'e': 5}, 'f': 6}

  with pytest.raises(MergeError):
    merge_dicts_without_duplicates(dict1, dict2)
  assert 'Duplicate key \'b->c\'' in caplog.text

def test_merge_dicts_without_duplicates__duplicate_different_types(caplog):
  dict1 = {'a': 1, 'b': 2}
  dict2 = {'b': [3, 4], 'c': 5}

  with pytest.raises(MergeError):
    merge_dicts_without_duplicates(dict1, dict2)
  assert 'Duplicate key \'b\'' in caplog.text

def test_merge_dicts_without_duplicates__duplicate_different_types_2(caplog):
  dict1 = {'a': 1, 'b': [3, 4]}
  dict2 = {'b': 2, 'c': 5}

  with pytest.raises(MergeError):
    merge_dicts_without_duplicates(dict1, dict2)
  assert 'Duplicate key \'b\'' in caplog.text

def test_merge_dicts_without_duplicates__with_list():
  dict1 = {'a': 1, 'b': [2, 3]}
  dict2 = {'c': 6}

  result = merge_dicts_without_duplicates(dict1, dict2)
  assert result == {'a': 1, 'b': [2, 3], 'c': 6}

def test_merge_dicts_without_duplicates__with_list_duplicate(caplog):
  dict1 = {'a': 1, 'b': [2, 3]}
  dict2 = {'b': {'c': 4}, 'd': 5}

  with pytest.raises(MergeError):
    merge_dicts_without_duplicates(dict1, dict2)
  assert 'Duplicate key \'b\'' in caplog.text

def test_merge_dicts_without_duplicates__with_list_extend_duplicate(caplog):
  dict1 = {'a': 1, 'b': [2, 3]}
  dict2 = {'b': [3, 4], 'c': 5}

  with pytest.raises(MergeError):
    merge_dicts_without_duplicates(dict1, dict2)
  assert 'Duplicate item \'b->[1]\'' in caplog.text

def test_merge_dicts_without_duplicates__with_list_extend_simple():
  dict1 = {'a': 1, 'b': [2, 3]}
  dict2 = {'b': [4, 5], 'c': 6}

  result = merge_dicts_without_duplicates(dict1, dict2)
  assert result == {'a': 1, 'b': [2, 3, 4, 5], 'c': 6}

def test_merge_dicts_without_duplicates__with_list_of_list_extend():
  dict1 = {'a': 1, 'b': [[2, 3], [4, 5]]}
  dict2 = {'b': [[6, 7], [8, 9]], 'c': 10}

  result = merge_dicts_without_duplicates(dict1, dict2)
  assert result == {'a': 1, 'b': [[2, 3], [4, 5], [6, 7], [8, 9]], 'c': 10}

def test_merge_dicts_without_duplicates__with_list_of_list_extend_duplicate(caplog):
  dict1 = {'a': 1, 'b': [[2, 3], [4, 5]]}
  dict2 = {'b': [[4, 5], [8, 9]], 'c': 10}

  with pytest.raises(MergeError):
    merge_dicts_without_duplicates(dict1, dict2)
  assert 'Duplicate item \'b->[1]\'' in caplog.text

def test_merge_dicts_without_duplicates__with_list_of_dicts_extend():
  dict1 = {'a': 1, 'b': [{'x': 2}, {'y': 3}]}
  dict2 = {'b': [{'z': 4}, {'w': 5}], 'c': 6}

  result = merge_dicts_without_duplicates(dict1, dict2)
  assert result == {'a': 1, 'b': [{'x': 2}, {'y': 3}, {'z': 4}, {'w': 5}], 'c': 6}

def test_merge_dicts_without_duplicates__with_list_of_dicts_extend_duplicate(caplog):
  dict1 = {'a': 1, 'b': [{'x': 2}, {'y': 3}]}
  dict2 = {'b': [{'y': 3}, {'w': 5}], 'c': 6}

  with pytest.raises(MergeError):
    merge_dicts_without_duplicates(dict1, dict2)
  assert 'Duplicate item \'b->[1]\'' in caplog.text

def test_merge_dicts_without_duplicates__with_list_of_dicts_extend_complex():
  dict1 = {'a': 1, 'b': [{'x': {'y': 2}}, {'z': 3}]}
  dict2 = {'b': [{'x': 2}, {'w': 5}], 'c': 6}

  result = merge_dicts_without_duplicates(dict1, dict2)
  assert result == {'a': 1, 'b': [{'x': {'y': 2}}, {'z': 3}, {'x': 2}, {'w': 5}], 'c': 6}

def test_merge_dicts_without_duplicates__with_list_of_dicts_extend_complex_duplicate(caplog):
  dict1 = {'a': 1, 'b': [{'x': {'y': 2}}, {'z': 3}]}
  dict2 = {'b': [{'x': {'y': 2}}, {'w': 5}], 'c': 6}

  with pytest.raises(MergeError):
    merge_dicts_without_duplicates(dict1, dict2)
  assert 'Duplicate item \'b->[0]\'' in caplog.text

###############
### merge_dicts_with_overrides
###############

def test_merge_dicts_with_overrides__non_nested():
  # Test merging two dictionaries with non-nested keys
  dict1 = {'a': 1, 'b': 2}
  dict2 = {'b': 3, 'c': 4}
  result = merge_dicts_with_overrides(dict1, dict2)
  assert result == {'a': 1, 'b': 3, 'c': 4}

def test_merge_dicts_with_overrides__nested():
  # Test merging dictionaries with nested keys
  dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
  dict2 = {'b': {'c': 4, 'e': 5}, 'f': 6}
  result = merge_dicts_with_overrides(dict1, dict2)
  assert result == {'a': 1, 'b': {'c': 4, 'd': 3, 'e': 5}, 'f': 6}

def test_merge_dicts_with_overrides__empty_left():
  # Test merging dictionaries with an empty dictionary on the left
  dict1 = {}
  dict2 = {'a': 1, 'b': 2}
  result = merge_dicts_with_overrides(dict1, dict2)
  assert result == {'a': 1, 'b': 2}

def test_merge_dicts_with_overrides__empty_right():
  # Test merging dictionaries with an empty dictionary on the right (should keep the dictionary on the left)
  dict1 = {'a': 1, 'b': 2}
  dict2 = {}
  result = merge_dicts_with_overrides(dict1, dict2)
  assert result == {'a': 1, 'b': 2}

def test_merge_dicts_with_overrides__both_empty():
  # Test merging two empty dictionaries
  dict1 = {}
  dict2 = {}
  result = merge_dicts_with_overrides(dict1, dict2)
  assert result == {}

def test_merge_dicts_with_overrides__empty_dict_on_right():
  # Test merging dictionaries with an empty dictionary on the right (should make it an empty dictionary on the left)
  dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
  dict2 = {'b': {}, 'f': None, 'g': 7}
  result = merge_dicts_with_overrides(dict1, dict2)
  assert result == {'a': 1, 'b': {}, 'f': None, 'g': 7}

def test_merge_dicts_with_overrides__none_value_on_right():
  # Test merging dictionaries with a None value on the right (should delete the key on the left)
  dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
  dict2 = {'b': None, 'f': 6}
  result = merge_dicts_with_overrides(dict1, dict2)
  assert result == {'a': 1, 'f': 6}

def test_merge_dicts_with_overrides__empty_dict_and_none_value():
  # Test merging dictionaries with a mix of empty dictionary and None value (should behave accordingly)
  dict1 = {'a': {}, 'b': None, 'c': 3}
  dict2 = {'a': {'x': 1}, 'b': 2, 'd': {}}
  result = merge_dicts_with_overrides(dict1, dict2)
  assert result == {'c': 3, 'a': {'x': 1}, 'b': 2, 'd': {}}

def test_merge_dicts_with_overrides__nested_dicts():
  # Test merging dictionaries with nested dictionaries
  dict1 = {'a': {'b': {'c': 1, 'd': 2}}, 'e': 3}
  dict2 = {'a': {'b': {'d': 4, 'e': 5}}, 'f': 6}
  result = merge_dicts_with_overrides(dict1, dict2)
  assert result == {'a': {'b': {'c': 1, 'd': 4, 'e': 5}}, 'e': 3, 'f': 6}

def test_merge_dicts_with_overrides__empty_nested_dict_on_right():
  # Test merging dictionaries with an empty nested dictionary on the right (should make it empty on the left)
  dict1 = {'a': {'b': {'c': 1, 'd': 2}}}
  dict2 = {'a': {'b': {}}}
  result = merge_dicts_with_overrides(dict1, dict2)
  assert result == {'a': {'b': {}}}

def test_merge_dicts_with_overrides__three_dicts():
  # Test merging three dictionaries with various corner cases
  dict1 = {'a': 1, 'b': 2, 'c': {'x': 10, 'y': 20}}
  dict2 = {'b': 3, 'c': {'x': 30, 'z': 40}, 'd': 4}
  dict3 = {'c': {'z': 300, 'w': 400}, 'e': 5}

  # Merging dict1, dict2, and dict3
  result = merge_dicts_with_overrides(dict1, dict2, dict3)

  # 'a' and 'd' keys from dict1, 'e' key from dict3, and 'w' key from dict3 should be in the result
  # 'b' key should take the value from dict2, 'c' key should merge values from all dictionaries
  assert result == {'a': 1, 'b': 3, 'c': {'x': 30, 'y': 20, 'z': 300, 'w': 400}, 'd': 4, 'e': 5}

def test_merge_dicts_with_overrides__three_empty_dicts():
  # Test merging three empty dictionaries
  dict1 = {}
  dict2 = {}
  dict3 = {}

  # Merging three empty dictionaries should result in an empty dictionary
  result = merge_dicts_with_overrides(dict1, dict2, dict3)
  assert result == {}

def test_merge_dicts_with_overrides__three_nested_dicts():
  # Test merging three dictionaries with nested dictionaries
  dict1 = {'a': {'x': 1, 'y': {'z': 2}}}
  dict2 = {'a': {'y': {'z': 3, 'w': 4}}}
  dict3 = {'a': {'w': 5, 'u': {'v': 6}}}

  # Merging dict1, dict2, and dict3
  result = merge_dicts_with_overrides(dict1, dict2, dict3)

  # Merged dictionaries should contain all keys and nested dictionaries
  assert result == {'a': {'x': 1, 'y': {'z': 3, 'w': 4}, 'w': 5, 'u': {'v': 6}}}

def test_merge_dicts_with_overrides__three_empty_nested_dict():
  # Test merging three dictionaries with empty nested dictionaries
  dict1 = {'a': {}}
  dict2 = {'a': {'x': 1}}
  dict3 = {'a': {'y': 2, 'z': {}}}

  # Merging dict1, dict2, and dict3
  result = merge_dicts_with_overrides(dict1, dict2, dict3)

  # Merged dictionaries should contain empty nested dictionary
  assert result == {'a': {'x': 1, 'y': 2, 'z': {}}}

def test_merge_dicts_with_overrides__three_dicts_with_none():
  # Test merging three dictionaries with various scenarios involving None values
  dict1 = {'a': 1, 'b': 2, 'c': {'x': 10, 'y': 20}}
  dict2 = {'b': 3, 'c': {'x': None, 'z': 40}, 'd': None}
  dict3 = {'c': {'z': 300, 'w': 400}, 'e': None}

  # Merging dict1, dict2, and dict3
  result = merge_dicts_with_overrides(dict1, dict2, dict3)

  # 'a', 'd', and 'e' keys from dict1, 'd' key from dict2 should be removed
  # 'b' key should take the value from dict2, 'c' key should merge values from all dictionaries
  assert result == {'a': 1, 'b': 3, 'c': {'y': 20, 'z': 300, 'w': 400}, 'd': None, 'e': None}

def test_merge_dicts_with_overrides__three_nested_dicts_with_none():
  # Test merging three dictionaries with nested dictionaries containing None values
  dict1 = {'a': {'x': 1, 'y': {'z': 2, 'w': None}}}
  dict2 = {'a': {'y': {'z': 3, 'w': 4, 'v': None}}}
  dict3 = {'a': {'w': 5, 'u': {'v': 6, 'x': None}}}

  # Merging dict1, dict2, and dict3
  result = merge_dicts_with_overrides(dict1, dict2, dict3)

  # None values should override other values in the merged dictionaries
  assert result == {'a': {'x': 1, 'y': {'z': 3, 'w': 4, 'v': None}, 'w': 5, 'u': {'v': 6, 'x': None}}}

def test_merge_dicts_with_overrides__three_none_values():
  # Test merging three dictionaries with None values
  dict1 = {'a': None, 'b': {'x': None, 'y': 20}}
  dict2 = {'b': None, 'c': None, 'd': 4}
  dict3 = {'c': None, 'e': None}

  # Merging dict1, dict2, and dict3
  result = merge_dicts_with_overrides(dict1, dict2, dict3)

  # All keys with None values should be removed
  assert result == {'a': None, 'd': 4, 'e': None}

def test_merge_dicts_with_overrides__three_dicts_with_empty_nested():
  # Test merging three dictionaries with empty nested dictionaries
  dict1 = {'a': {'b': {}}, 'c': {'d': 1}}
  dict2 = {'a': {'b': {}}, 'c': {'d': 2}}
  dict3 = {'a': {'b': {}}, 'c': {'d': 3}}

  # Merging dict1, dict2, and dict3
  result = merge_dicts_with_overrides(dict1, dict2, dict3)

  # Merged dictionaries should contain empty nested dictionaries
  assert result == {'a': {'b': {}}, 'c': {'d': 3}}

def test_merge_dicts_with_overrides__non_nested_and_nested_keys_with_none():
  # Test merging dictionaries with non-nested and nested keys, and None values
  dict1 = {'a': 1, 'b': {'c': 2, 'd': 3, 'e': None}}
  dict2 = {'b': {'c': 4, 'e': 5, 'f': None}, 'g': 6}
  dict3 = {'h': None, 'i': {'j': 7, 'k': None}}
  result = merge_dicts_with_overrides(dict1, dict2, dict3)
  assert result == {'a': 1, 'b': {'c': 4, 'd': 3, 'e': 5, 'f': None}, 'g': 6, 'h': None, 'i': {'j': 7, 'k': None}}

def test_merge_dicts_with_overrides__deeply_nested_keys():
  # Test merging dictionaries with deeply nested keys
  dict1 = {'a': {'b': {'c': {'d': {'e': 1}}}}}
  dict2 = {'a': {'b': {'c': {'d': {'f': 2}}}}}
  dict3 = {'a': {'b': {'c': {'d': {'g': 3}}}}}
  result = merge_dicts_with_overrides(dict1, dict2, dict3)
  assert result == {'a': {'b': {'c': {'d': {'e': 1, 'f': 2, 'g': 3}}}}}

def test_merge_dicts_with_overrides__empty_nested_and_none_values():
  # Test merging dictionaries with empty nested dictionaries and None values
  dict1 = {'a': {'b': {}}, 'c': {'d': 1, 'e': None}}
  dict2 = {'a': {'b': {'f': None}}, 'c': {'d': 2, 'e': 3}}
  dict3 = {'a': {'b': {'g': None}}, 'c': {'d': None, 'h': 4}}
  result = merge_dicts_with_overrides(dict1, dict2, dict3)
  assert result == {'a': {'b': {'f': None, 'g': None}}, 'c': {'e': 3, 'h': 4}}

################
### VarsResolver
################

def test_vars_resolver_empty_vars():
  resolver = VarsResolver()
  vars = {}
  result = resolver.resolve(vars, vars)
  assert result == {}
  assert resolver.get_resolutions() == 0

def test_vars_resolver_single_var():
  resolver = VarsResolver()
  vars = {'var1': 'value1'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value1'}
  assert resolver.get_resolutions() == 0

def test_vars_resolver_multiple_vars():
  resolver = VarsResolver()
  vars = {'var1': 'value1', 'var2': 'value2', 'var3': 'value3'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value1', 'var2': 'value2', 'var3': 'value3'}
  assert resolver.get_resolutions() == 0

def test_vars_resolver_nested_vars():
  resolver = VarsResolver()
  vars = {'var1': 'value1', 'var2': {'var3': 'value3'}}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value1', 'var2': {'var3': 'value3'}}
  assert resolver.get_resolutions() == 0

def test_vars_resolver_var_with_resolvable_var():
  resolver = VarsResolver()
  vars = {'var1': '${var2}', 'var2': 'value2'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value2', 'var2': 'value2'}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_with_multiple_resolvable_var_with_concat():
  resolver = VarsResolver()
  vars = {'var1': '${var2}/${var3}', 'var2': 'value2', 'var3': 'value3'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value2/value3', 'var2': 'value2', 'var3': 'value3'}
  assert resolver.get_resolutions() == 2

def test_vars_resolver_var_with_resolvable_var_with_concat_left():
  resolver = VarsResolver()
  vars = {'var1': ' ${var2}', 'var2': 'value2'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': ' value2', 'var2': 'value2'}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_with_resolvable_var_with_concat_right():
  resolver = VarsResolver()
  vars = {'var1': '${var2} ', 'var2': 'value2'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value2 ', 'var2': 'value2'}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_with_multiple_resolvable_vars():
  resolver = VarsResolver()
  vars = {'var1': '${var2}', 'var2': 'value2', 'var3': '${var4}', 'var4': 'value4'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value2', 'var2': 'value2', 'var3': 'value4', 'var4': 'value4'}
  assert resolver.get_resolutions() == 2

def test_vars_resolver_value_with_unresolvable_var(caplog):
  resolver = VarsResolver()
  vars = {'var1': '${var2}'}
  with pytest.raises(ConfigFileError):
    resolver.resolve(vars, vars)
  assert 'Variable ${var2} not found in vars' in caplog.text

def test_vars_resolver__allow_unresolved_vars_simple(caplog):
  resolver = VarsResolver()
  vars = {'var1': '${var2}'}
  result = resolver.resolve(vars, vars, True)
  assert result == {'var1': '${var2}'}

def test_vars_resolver__allow_unresolved_vars_in_string(caplog):
  resolver = VarsResolver()
  vars = {'var1': 'before${var2}after'}
  result = resolver.resolve(vars, vars, True)
  assert result == {'var1': 'before${var2}after'}

def test_vars_resolver__allow_unresolved_vars_multiple_vars(caplog):
  resolver = VarsResolver()
  vars = {'var1': '${var3}bef${var3}ore${var2}aft${var5}er${var5}', 'var3':'value3', 'var5': 'value5'}
  result = resolver.resolve(vars, vars, True)
  assert result == {'var1': 'value3befvalue3ore${var2}aftvalue5ervalue5', 'var3':'value3', 'var5': 'value5'}

def test_vars_resolver_var_with_resolvable_var_dict():
  resolver = VarsResolver()
  vars = {'var1': '${var2}', 'var2': {'var3': 'value3'}}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': {'var3': 'value3'}, 'var2': {'var3': 'value3'}}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_with_resolvable_var_list():
  resolver = VarsResolver()
  vars = {'var1': '${var2}', 'var2': ['value2']}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': ['value2'], 'var2': ['value2']}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_with_nested_resolvable_vars():
  resolver = VarsResolver()
  vars = {'var1': '${var2}', 'var2': '${var3}', 'var3': 'value3'}
  result = VarsResolver().resolve_all(vars, vars)
  assert result == {'var1': 'value3', 'var2': 'value3', 'var3': 'value3'}

def test_vars_resolver_var_with_resolvable_var_complex_key():
  resolver = VarsResolver()
  vars = {'var1': '${var2[var3]}', 'var2': {'var3': 'value3'}}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value3', 'var2': {'var3': 'value3'}}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_from_different_source():
  resolver = VarsResolver()
  vars = {'var1': '${var2}'}
  vars_source ={'var2': 'value2'}
  result = resolver.resolve(vars, vars_source)
  assert result == {'var1': 'value2'}
  assert resolver.get_resolutions() == 1

################
### get_module_name
################

def test__get_module_name():
  assert get_module_name() == 'make_argocd_fly'

################
### get_package_name
################

def test__get_package_name():
  assert get_package_name() == 'make-argocd-fly'

################
### build_path
################

def test_build_path_with_relative_path_in_current_directory(tmp_path):
  root_dir = tmp_path
  path = 'config.py'
  expected = tmp_path / 'config.py'
  expected.write_text('test')

  assert build_path(root_dir, path) == str(expected)

def test_build_path_with_absolute_path_in_current_directory(tmp_path):
  root_dir = tmp_path
  path = tmp_path / 'config.py'
  expected = tmp_path / 'config.py'
  expected.write_text('test')

  assert build_path(root_dir, path) == expected

def test_build_path_with_relative_path_in_subdirectory(tmp_path):
  root_dir = tmp_path
  src_dir = tmp_path / 'source'
  src_dir.mkdir()
  path = 'source/app.py'
  expected = tmp_path / 'source/app.py'
  expected.write_text('test')

  assert build_path(str(root_dir), path) == str(expected)

def test_build_path_with_absolute_path_in_subdirectory(tmp_path):
  root_dir = tmp_path
  src_dir = tmp_path / 'source'
  src_dir.mkdir()
  path = tmp_path / 'source/app.py'
  expected = tmp_path / 'source/app.py'
  expected.write_text('test')

  assert build_path(root_dir, path) == expected

def test_build_path_with_empty_path(tmp_path, caplog):
  root_dir = tmp_path
  path = ''

  with pytest.raises(InternalError):
    build_path(root_dir, path)
  assert 'Path is empty' in caplog.text

def test_build_path_with_none_path(tmp_path, caplog):
  root_dir = tmp_path
  path = None

  with pytest.raises(InternalError):
    build_path(root_dir, path)
  assert 'Path is empty' in caplog.text

def test_build_path_with_nonexistent_path(tmp_path, caplog):
  root_dir = str(tmp_path)
  path = 'nonexistent_file.py'
  non_existent_path = tmp_path / 'nonexistent_file.py'

  with pytest.raises(InternalError):
    build_path(root_dir, path)
  assert f'Path does not exist: {non_existent_path}' in caplog.text

def test_build_path_with_nonexistent_path_allow_missing(tmp_path, caplog):
  root_dir = str(tmp_path)
  path = 'nonexistent_file.py'
  non_existent_path = tmp_path / 'nonexistent_file.py'

  assert build_path(root_dir, path, allow_missing=True) == str(non_existent_path)

################
### extract_undefined_variable
################

def test_extract_undefined_variable__jinja2_variable():
  variable_name = 'test_variable'
  message = f'\'{variable_name}\' is undefined'

  assert extract_undefined_variable(message) == variable_name

def test_extract_undefined_variable__jinja2_attribute():
  variable_name = 'test_attribute'
  message = f'has no attribute \'{variable_name}\''

  assert extract_undefined_variable(message) == variable_name

def test_extract_undefined_variable__exception():
  message = 'random message'

  with pytest.raises(UnknownJinja2Error):
    extract_undefined_variable(message)
