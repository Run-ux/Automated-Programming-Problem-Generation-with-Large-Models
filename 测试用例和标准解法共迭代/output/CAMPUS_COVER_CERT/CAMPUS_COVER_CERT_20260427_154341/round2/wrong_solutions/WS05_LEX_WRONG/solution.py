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
            found = False
            for R in range(K - 1, -1, -1):
                for L in range(R + 1):
                    cnt = 0
                    for _, a_val in teams:
                        r1, r2 = a_val % x, (a_val + 1) % x
                        if (L <= r1 <= R) or (L <= r2 <= R) or (r1 + x <= R) or (r2 + x <= R):
                            cnt += 1
                    if cnt < R - L + 1:
                        out.append("NO")
                        out.append(f"{L} {R}")
                        found = True
                        break
                if found: break
            if not found:
                out.append("YES")
                for s in range(K):
                    out.append(f"1 {s}")
    return "\n".join(out)