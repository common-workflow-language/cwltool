from _typeshed import Incomplete
from prov.model import PROV_ATTR_ACTIVITY as PROV_ATTR_ACTIVITY
from prov.model import PROV_ATTR_AGENT as PROV_ATTR_AGENT
from prov.model import PROV_ATTR_ALTERNATE1 as PROV_ATTR_ALTERNATE1
from prov.model import PROV_ATTR_ALTERNATE2 as PROV_ATTR_ALTERNATE2
from prov.model import PROV_ATTR_COLLECTION as PROV_ATTR_COLLECTION
from prov.model import PROV_ATTR_DELEGATE as PROV_ATTR_DELEGATE
from prov.model import PROV_ATTR_ENTITY as PROV_ATTR_ENTITY
from prov.model import PROV_ATTR_GENERAL_ENTITY as PROV_ATTR_GENERAL_ENTITY
from prov.model import PROV_ATTR_GENERATED_ENTITY as PROV_ATTR_GENERATED_ENTITY
from prov.model import PROV_ATTR_INFORMANT as PROV_ATTR_INFORMANT
from prov.model import PROV_ATTR_INFORMED as PROV_ATTR_INFORMED
from prov.model import PROV_ATTR_RESPONSIBLE as PROV_ATTR_RESPONSIBLE
from prov.model import PROV_ATTR_SPECIFIC_ENTITY as PROV_ATTR_SPECIFIC_ENTITY
from prov.model import PROV_ATTR_TRIGGER as PROV_ATTR_TRIGGER
from prov.model import PROV_ATTR_USED_ENTITY as PROV_ATTR_USED_ENTITY
from prov.model import ProvActivity as ProvActivity
from prov.model import ProvAgent as ProvAgent
from prov.model import ProvDocument as ProvDocument
from prov.model import ProvElement as ProvElement
from prov.model import ProvEntity as ProvEntity
from prov.model import ProvRecord as ProvRecord
from prov.model import ProvRelation as ProvRelation

INFERRED_ELEMENT_CLASS: Incomplete

def prov_to_graph(prov_document): ...
def graph_to_prov(g): ...
