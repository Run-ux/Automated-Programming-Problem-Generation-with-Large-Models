def solve(input_str: str) -> str:
    import sys
    data = list(map(int, input_str.split()))
    it = iter(data)
    x = next(it)
    q = next(it)
    teams = []
    out = []
    for _ in range(q):
        t = next(it)
        v = next(it)
        if t == 1:
            teams.append(v)
        else:
            K = v
            if len(teams) < K:
                out.append("NO")
                out.append(f"0 {K-1}")
                continue
            assignment = {}
            used_teams = set()
            possible = True
            fail_s = 0
            for s in range(K):
                assigned_team = -1
                for idx, a in enumerate(teams):
                    r1, r2 = a % x, (a + 1) % x
                    if idx not in used_teams and (s % x == r1 or s % x == r2):
                        assigned_team = idx
                        break
                if assigned_team != -1:
                    used_teams.add(assigned_team)
                    assignment[s] = assigned_team
                else:
                    possible = False
                    fail_s = s
                    break
            if possible:
                out.append("YES")
                for s in range(K):
                    out.append(f"{assignment[s]+1} {s}")
            else:
                out.append("NO")
                out.append(f"{fail_s} {K-1}")
    return "\n".join(out)