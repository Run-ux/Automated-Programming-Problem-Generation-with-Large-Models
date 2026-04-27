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
            conflict_L, conflict_R = 0, K - 1
            for R in range(K):
                cnt = 0
                for _, a_val in teams:
                    r1, r2 = a_val % x, (a_val + 1) % x
                    if r1 <= R or r2 <= R or r1 + x <= R or r2 + x <= R:
                        cnt += 1
                if cnt < R + 1:
                    conflict_L, conflict_R = 0, R
                    break
            if conflict_L == 0 and conflict_R == K - 1 and len(teams) >= K:
                out.append("YES")
                for s in range(K):
                    out.append(f"{teams[s % len(teams)][0]} {s}")
            else:
                out.append("NO")
                out.append(f"{conflict_L} {conflict_R}")
    return "\n".join(out)