from src.shared.utility.l.xshop.index import index as xshop_index


async def index(_p={'data': {}}):
    return await xshop_index(_p)
