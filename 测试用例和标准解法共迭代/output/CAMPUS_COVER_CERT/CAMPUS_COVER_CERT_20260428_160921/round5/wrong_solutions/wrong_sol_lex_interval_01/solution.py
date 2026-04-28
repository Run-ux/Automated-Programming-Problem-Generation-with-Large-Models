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
            if len(teams) < K:
                output.append("NO")
                output.append(f"0 {K-1}")
                continue
            cover = [False]*x
            for _, a in teams:
                r = a % x
                cover[r] = True
                cover[(r+1)%x] = True
            all_covered = True
            for r in range(min(x, K)):
                if not cover[r]:
                    all_covered = False
                    break
            if all_covered:
                output.append("YES")
                used = [False]*len(teams)
                assign = []
                possible = True
                for s in range(K):
                    found = -1
                    for idx, (tid, a) in enumerate(teams):
                        if not used[idx] and (s % x == a % x or s % x == (a+1) % x):
                            found = idx
                            break
                    if found == -1:
                        possible = False
                        break
                    used[found] = True
                    assign.append((tid, s))
                if possible:
                    for tid, s in assign:
                        output.append(f"{tid} {s}")
                else:
                    for s in range(K):
                        for tid, a in teams:
                            if s % x == a % x or s % x == (a+1) % x:
                                output.append(f"{tid} {s}")
                                break
                        else:
                            output.append(f"{teams[0][0]} {s}")
            else:
                output.append("NO")
                output.append(f"0 {K-1}")
    return '\n'.join(output)