class TreeNode(ParentT, Generic[T]):
    """A tree node with a name, parent, status, importance, and report."""
    name: str = Field(default_factory=compose(str, uuid.uuid4))
    parent: Optional["ref[TreeNode[T]]"] | None = None
    root: Optional["ref[TreeNode[T]]"] | None = None
    status: Literal["waiting", "running", "done"] | None = None
    importance: float = 1.0
    report: str | None = None
    """A report on the status of the subtree."""
    children: Dict[str, "TreeNode[T]"] = Field(default_factory=dict)
    adjacency_list: Dict[str, set[str]] = Field(default_factory=dict)
    reverse_adjacency_list: Dict[str, set[str]] = Field(default_factory=dict)
    nxgraph: nx.DiGraph | None = None
    value: T | None = None
    Type: type[T]
    
    @model_validator(mode="before")
    @classmethod
    def makerefs(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if "parent" in v:
            v["parent"] = ref(v["parent"])
        if "root" in v:
            v["root"] = ref(v["root"])
        return v
    @classmethod
    def from_item(cls, item: Tuple[str, T],name=None, parent=None) -> "TreeNode":
        return cls(*item,name=name, parent=parent)
    
    @classmethod
    def from_dict(cls, d: dict, name=None, parent=None) -> "TreeNode":
        return cls(name=name or d.pop("name",None), parent=parent or d.pop("parent",None), **d)
  
    @classmethod
    def __class_getitem__(cls, value_type: T) -> type[Self]:
        cls.Type = value_type
        return cls
    
    def __setitem__(self, key, value):
        return self.__setattr__(key, value)
 
    def graph(self,g: nx.DiGraph=None) -> nx.DiGraph:
        """Recursively adds nodes and edges to a NetworkX graph."""
        g = g or nx.DiGraph()
        g.add_node(self.name)
       
        for child in self.children.values():
            child.graph(g)
        return g

    class GraphDict(TypedDict):
            name: str
            parent: Optional["ref[TreeNode[T]]"]
            status: Literal["waiting", "running", "done"] | None
            report: str | None
            children: dict[str, "TreeNode[T]"]
            adjacency_list: dict[str, set[str]]
            reverse_adjacency_list: dict[str, set[str]]
            nxgraph: nx.DiGraph
            value: T
            Type: T

    def dict(self) -> GraphDict:
        return self.dict()
    if TYPE_CHECKING:
        
    
        
        @property
        def name(self) -> str:
            return self.name

        def __iter__(self):
            class GraphTuple(NamedTuple):
                name: str
                parent: "ref[TreeNode[T]]" | None
                status: Literal["waiting", "running", "done"] | None
                report: str | None
                children: dict[str, "TreeNode[T]"]
                adjacency_list: dict[str, set[str]]
                reverse_adjacency_list: dict[str, set[str]]
                nxgraph: nx.DiGraph
                value: T
                Type: T
            return GraphTuple( ).__iter__()
        