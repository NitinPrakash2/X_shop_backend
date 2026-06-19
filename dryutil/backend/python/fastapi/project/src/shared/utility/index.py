from src.shared.util.include_file.index import include_file


async def index(_p={'data': {}}):
    lib_name, _lib_ = include_file("src/shared/utility/l/706/index.py", lambda name, module: ())[0]
    return await _lib_.index(_p)
