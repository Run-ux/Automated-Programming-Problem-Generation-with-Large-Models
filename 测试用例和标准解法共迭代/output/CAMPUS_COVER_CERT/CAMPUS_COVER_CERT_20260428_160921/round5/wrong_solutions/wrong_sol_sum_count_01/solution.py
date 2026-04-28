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
            cnt = [0]*x
            for _, a in teams:
                cnt[a % x] += 1
            occ = [K//x]*x
            for r in range(K % x):
                occ[r] += 1
            total = 0
            for r in range(x):
                total += cnt[r] * (occ[r] + occ[(r+1)%x])
            if total >= K:
                output.append("YES")
                for s in range(K):
                    assigned = False
                    for tid, a in teams:
                        if s % x == a % x or s % x == (a+1) % x:
                            output.append(f"{tid} {s}")
                            assigned = True
                            break
                    if not assigned:
                        output.append(f"{teams[0][0]} {s}")
            else:
                output.append("NO")
                output.append(f"0 {K-1}")
    return '\n'.join(output)