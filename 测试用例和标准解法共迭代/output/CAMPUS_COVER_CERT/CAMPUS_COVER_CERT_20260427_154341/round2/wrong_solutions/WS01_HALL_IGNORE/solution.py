import sys

def solve(input_str: str) -> str:
    tokens = input_str.split()
    it = iter(tokens)
    x = int(next(it))
    q = int(next(it))
    teams = []
    out = []
    tid = 1
    for _ in range(q):
        op = int(next(it))
        if op == 1:
            a = int(next(it))
            teams.append((tid, a))
            tid += 1
        else:
            K = int(next(it))
            if len(teams) < K:
                out.append("NO")
                out.append(f"0 {K-1}")
            else:
                out.append("YES")
                used = set()
                for t_id, a_val in teams:
                    r1, r2 = a_val % x, (a_val + 1) % x
                    for s in [r1, r2]:
                        if s < K and s not in used:
                            out.append(f"{t_id} {s}")
                            used.add(s)
                            break
                for s in range(K):
                    if s not in used:
                        out.append(f"{teams[0][0]} {s}")
                        used.add(s)
    return "\n".join(out)