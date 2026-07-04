from enum import StrEnum


class ExperimentalFeature(StrEnum):
  INCREMENTAL_OUTPUT = 'incremental-output'


def parse_experimental(value: str | None) -> tuple[set[ExperimentalFeature], list[str]]:
  if not value:
    return set(), []

  features: set[ExperimentalFeature] = set()
  unknown = []
  known_values = {feature.value: feature for feature in ExperimentalFeature}

  for raw_feature in value.split(','):
    feature = raw_feature.strip()
    if not feature:
      continue

    if feature in known_values:
      features.add(known_values[feature])
    else:
      unknown.append(feature)

  return features, unknown
