import inspect


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.4f}"
    return repr(v)

def dbg(*args):
    frame = inspect.currentframe().f_back
    info = inspect.getframeinfo(frame)

    call = info.code_context[0]
    inside = call.split("dbg(",1)[1].rsplit(")",1)[0]
    names = [x.strip() for x in inside.split(",")]

    prefix = f"[{info.filename}:{info.lineno}]"

    parts = [f"{n}={_fmt(v)}" for n, v in zip(names, args)]
    print(prefix, " ".join(parts))

    return args[0] if len(args) == 1 else args