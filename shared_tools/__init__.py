__all__ = [
    "CopyFile",
    "ExecuteTool",
    "FindTools",
    "GetMarketDataSnapshot",
    "ManageConnections",
    "SearchTools",
]


def __getattr__(name: str):
    if name == "CopyFile":
        from shared_tools.CopyFile import CopyFile

        return CopyFile
    if name == "ExecuteTool":
        from shared_tools.ExecuteTool import ExecuteTool

        return ExecuteTool
    if name == "FindTools":
        from shared_tools.FindTools import FindTools

        return FindTools
    if name == "GetMarketDataSnapshot":
        from shared_tools.GetMarketDataSnapshot import GetMarketDataSnapshot

        return GetMarketDataSnapshot
    if name == "ManageConnections":
        from shared_tools.ManageConnections import ManageConnections

        return ManageConnections
    if name == "SearchTools":
        from shared_tools.SearchTools import SearchTools

        return SearchTools
    raise AttributeError(f"module 'shared_tools' has no attribute {name!r}")
