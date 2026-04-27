import sys

def solve(input_str: str) -> str:
    data = input_str.split()
    it = iter(data)
    x = int(next(it))
    q = int(next(it))
    teams = []
    out = []

    for _ in range(q):
        op = int(next(it))
        val = int(next(it))
        if op == 1:
            teams.append((len(teams)+1, val))
        else:
            K = val
            conflict_found = False
            # 缺陷：仅检查 L=0 的前缀区间，忽略字典序最小要求
            for R in range(K):
                count = 0
                for idx, a in teams:
                    s1, s2 = a % x, (a + 1) % x
                    if s1 <= R or s2 <= R:
                        count += 1
                if count < R + 1:
                    out.append("NO")
                    out.append(f"0 {R}")
                    conflict_found = True
                    break
            if not conflict_found:
                out.append("YES")
                used = set()
                for s in range(K):
                    for idx, a in teams:
                        if idx not in used and (s % x == a % x or s % x == (a + 1) % x):
                            out.append(f"{idx} {s}")
                            used.add(idx)
                            break
    return "\n".join(out)