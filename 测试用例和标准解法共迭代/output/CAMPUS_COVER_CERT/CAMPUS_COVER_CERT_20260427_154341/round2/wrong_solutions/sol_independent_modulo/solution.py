import sys

def solve(input_str: str) -> str:
    data = input_str.split()
    it = iter(data)
    try:
        x = int(next(it))
        q = int(next(it))
    except StopIteration:
        return ""

    cnt = [0] * x
    teams = []
    out = []

    for _ in range(q):
        t = int(next(it))
        val = int(next(it))
        if t == 1:
            teams.append((len(teams)+1, val))
            cnt[val % x] += 1
        else:
            K = val
            full = K // x
            rem = K % x
            possible = True
            for r in range(x):
                need = full + (1 if r < rem else 0)
                if cnt[r] < need:
                    possible = False
                    break
            if possible:
                out.append("YES")
                used = set()
                for s in range(K):
                    r = s % x
                    assigned = False
                    for idx, a in teams:
                        if idx not in used and a % x == r:
                            out.append(f"{idx} {s}")
                            used.add(idx)
                            assigned = True
                            break
                    if not assigned:
                        for idx, a in teams:
                            if idx not in used and (a + 1) % x == r:
                                out.append(f"{idx} {s}")
                                used.add(idx)
                                break
            else:
                out.append("NO")
                out.append(f"0 {K-1}")
    return "\n".join(out)