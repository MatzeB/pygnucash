def full_acc_name(acc, maxdepth=1000):
    if acc.parent is None or maxdepth == 0:
        return ""
    result = full_acc_name(acc.parent, maxdepth - 1)
    if result != "":
        result += ":"
    result += acc.name
    return result
