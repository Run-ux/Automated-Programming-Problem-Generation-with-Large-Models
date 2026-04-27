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
            covered = set()
            for t_id, a_val in teams:
                for p in [a_val, a_val + 1]:
                    if p < K:
                        covered.add((p, t_id))
            if len(covered) < K:
                out.append("NO")
                out.append(f"0 {K-1}")
            else:
                out.append("YES")
                assigned = {}
                for p, t_id in sorted(covered):
                    if p not in assigned:
                        assigned[p] = t_id
                for s in range(K):
                    out.append(f"{assigned.get(s, teams[0][0])} {s}")
    return "\n".join(out)