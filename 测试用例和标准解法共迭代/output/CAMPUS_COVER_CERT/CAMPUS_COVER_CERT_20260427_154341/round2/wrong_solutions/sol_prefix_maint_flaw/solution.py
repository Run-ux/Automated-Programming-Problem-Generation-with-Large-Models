import sys

def solve(input_str: str) -> str:
    data = input_str.split()
    it = iter(data)
    x = int(next(it))
    q = int(next(it))
    cnt = [0] * x
    teams = []
    out = []

    for _ in range(q):
        op = int(next(it))
        val = int(next(it))
        if op == 1:
            teams.append(val)
            cnt[val % x] += 1
            cnt[(val + 1) % x] += 1
        else:
            K = val
            # 缺陷：静态计算前缀盈余极值，错误地将周期盈余映射到线性区间，未正确维护动态极值位置
            min_val = 0
            min_idx = 0
            cur = 0
            for i in range(x):
                cur += cnt[i] - 1
                if cur < min_val:
                    min_val = cur
                    min_idx = i

            if min_val < 0:
                L = (min_idx + 1) % x
                out.append("NO")
                out.append(f"{L} {K-1}")
            else:
                out.append("YES")
                used = set()
                for s in range(K):
                    for idx, a in enumerate(teams, 1):
                        if idx not in used and (s % x == a % x or s % x == (a + 1) % x):
                            out.append(f"{idx} {s}")
                            used.add(idx)
                            break
    return "\n".join(out)