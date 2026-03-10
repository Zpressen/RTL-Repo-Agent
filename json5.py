import json

JSONDecodeError = json.JSONDecodeError


def loads(s, *args, **kwargs):
    return json.loads(s, *args, **kwargs)


def load(fp, *args, **kwargs):
    return json.load(fp, *args, **kwargs)


def dumps(obj, *args, **kwargs):
    return json.dumps(obj, *args, **kwargs)


def dump(obj, fp, *args, **kwargs):
    return json.dump(obj, fp, *args, **kwargs)
