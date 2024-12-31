from make_argocd_fly.consts import AppParamsNames
from make_argocd_fly.utils import check_lists_equal


###################
### AppParamsNames
###################

def test_AppParamsNames__get_names():
  names = AppParamsNames.get_names()

  assert isinstance(names, list)
  assert check_lists_equal(names, ['app_deployer', 'app_deployer_env', 'non_k8s_files_to_render', 'exclude_rendering'])
