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
            if len(teams) < K:
                out.append("NO")
                out.append(f"0 {K-1}")
            else:
                out.append("YES")
                assigned_count = 0
                # 缺陷：直接按余数分配，未严格校验 s < K 与时段唯一性
                for idx, a in teams:
                    if assigned_count >= K:
                        break
                    s = a % x
                    if s >= K:
                        s = (a + 1) % x
                    # 未检查 s 是否已被当前查询的其他队伍占用，也未验证 s 是否真正满足同余条件与边界交集
                    out.append(f"{idx} {s}")
                    assigned_count += 1
    return "\n".join(out)