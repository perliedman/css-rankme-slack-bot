def bestPack(items):
    bestDiff = 1e9
    teams = []
    for x in xrange(1, 2**len(items) / 2 + 1):
        b = 1
        t1 = []
        t2 = []
        ts1 = 0
        ts2 = 0
        for n in items:
            if x & b:
                t1.append(n[0])
                ts1 += n[1]
            else:
                t2.append(n[0])
                ts2 += n[1]
            b = b << 1
        diff = abs(ts1 - ts2)
        teams.append(((t1, t2), diff))

    teams.sort(lambda a, b: cmp(a[1], b[1]))

    return teams
