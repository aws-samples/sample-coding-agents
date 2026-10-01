def f(x):
    r = []
    for i in x:
        if i % 2 == 0:
            r.append(i * 2)
    return r


def calc(a, b, c):
    if c == 'add':
        return a + b
    elif c == 'sub':
        return a - b
    elif c == 'mul':
        return a * b
    elif c == 'div':
        if b != 0:
            return a / b
        else:
            return None
    else:
        return None


class user:
    def __init__(self, n, e, a):
        self.n = n
        self.e = e
        self.a = a

    def getinfo(self):
        return self.n + " " + self.e + " " + str(self.a)
