import dataclasses
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field 

from endpoints.alignments import InfixType


class VariantFragment(BaseModel):
    fragment: dict
    infixType: str


class ClusteringAlgorithm(str, Enum):
    AGGLOMERATIVE_EDIT_DISTANCE_CLUSTERING = "AGGLOMERATIVE_EDIT_DISTANCE_CLUSTERING"
    LABEL_VECTOR_CLUSTERING = "LABEL_VECTOR_CLUSTERING"

class ClusteringConstraints(BaseModel):
    must_link: List[List[int]] = Field(default_factory=list, alias="mustLink")
    cannot_link: List[List[int]] = Field(default_factory=list, alias="cannotLink")

    class Config:
        allow_population_by_field_name = True

class ClusteringParameters(BaseModel):
    algorithm: ClusteringAlgorithm
    params: Dict
    constraints: Optional[ClusteringConstraints] = None


class HRRClusteringParameters(BaseModel):
    nClusters: int
    order: float = 1.0
    nesting: float = 1.0
    sameActivities: List[List[str]] = []
    ignoredActivities: List[str] = []
    mustLink: List[List[int]] = []
    cannotLink: List[List[int]] = []
    previousClusters: Dict[int, int] = {}
    fromScratch: bool = False


@dataclasses.dataclass
class VariantInformation:
    infix_type: InfixType
    is_user_defined: bool
