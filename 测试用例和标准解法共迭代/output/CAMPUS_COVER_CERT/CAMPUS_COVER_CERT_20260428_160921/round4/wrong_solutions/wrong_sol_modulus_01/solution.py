def solve(input_str: str) -> str:
    data = input_str.split()
    if not data:
        return ''
    it = iter(data)
    x = int(next(it))
    q = int(next(it))
    teams = []
    output = []
    for _ in range(q):
        op = int(next(it))
        if op == 1:
            a = int(next(it))
            teams.append((len(teams)+1, a))
        else:
            K = int(next(it))
            used = [False]*len(teams)
            assign = []
            possible = True
            for s in range(K):
                found = -1
                for idx, (tid, a) in enumerate(teams):
                    if not used[idx] and (a == s or a+1 == s):
                        found = idx
                        break
                if found == -1:
                    possible = False
                    output.append("NO")
                    output.append(f"{s} {s}")
                    break
                used[found] = True
                assign.append((tid, s))
            if possible:
                output.append("YES")
                for tid, s in assign:
                    output.append(f"{tid} {s}")
    return '\n'.join(output)