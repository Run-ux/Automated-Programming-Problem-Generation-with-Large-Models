def check(input_str: str, output_str: str, expected_str: str | None) -> bool:
    tokens = input_str.split()
    idx = 0
    try:
        x = int(tokens[idx]); idx += 1
        q = int(tokens[idx]); idx += 1
    except (ValueError, IndexError):
        return False
    if not (1 <= x <= 400000) or not (1 <= q <= 400000):
        return False
    ops = []
    for _ in range(q):
        if idx >= len(tokens):
            return False
        typ = int(tokens[idx]); idx += 1
        if typ == 1:
            if idx >= len(tokens):
                return False
            a = int(tokens[idx]); idx += 1
            if a < 0 or a > 1000000000:
                return False
            ops.append((1, a))
        elif typ == 2:
            if idx >= len(tokens):
                return False
            K = int(tokens[idx]); idx += 1
            if K < 1 or K > 1000000000:
                return False
            ops.append((2, K))
        else:
            return False
    if idx != len(tokens):
        return False

    out_lines = [line.strip() for line in output_str.splitlines() if line.strip() != '']
    exp_lines = None
    if expected_str is not None:
        exp_lines = [line.strip() for line in expected_str.splitlines() if line.strip() != '']

    teams = []
    teams_by_r = [set() for _ in range(x)]
    out_idx = 0
    exp_idx = 0

    for typ, val in ops:
        if typ == 1:
            a = val
            r1 = a % x
            r2 = (a + 1) % x
            teams.append((a, r1, r2))
            teams_by_r[r1].add(len(teams) - 1)
            teams_by_r[r2].add(len(teams) - 1)
        else:
            K = val
            if out_idx >= len(out_lines):
                return False
            first_line = out_lines[out_idx]; out_idx += 1
            if first_line == "YES":
                if out_idx + K > len(out_lines):
                    return False
                used_teams = set()
                covered_slots = set()
                for _ in range(K):
                    line = out_lines[out_idx]; out_idx += 1
                    parts = line.split()
                    if len(parts) != 2:
                        return False
                    try:
                        gid = int(parts[0])
                        s = int(parts[1])
                    except ValueError:
                        return False
                    if not (1 <= gid <= len(teams)):
                        return False
                    if gid in used_teams:
                        return False
                    if not (0 <= s < K):
                        return False
                    if s in covered_slots:
                        return False
                    a_team, r1, r2 = teams[gid - 1]
                    if s % x != r1 and s % x != r2:
                        return False
                    used_teams.add(gid)
                    covered_slots.add(s)
                if len(covered_slots) != K:
                    return False
                if exp_lines is not None:
                    if exp_idx >= len(exp_lines):
                        return False
                    if exp_lines[exp_idx] != "YES":
                        return False
                    exp_idx += 1
                    exp_idx += K
            elif first_line == "NO":
                if out_idx >= len(out_lines):
                    return False
                line = out_lines[out_idx]; out_idx += 1
                parts = line.split()
                if len(parts) != 2:
                    return False
                try:
                    L = int(parts[0])
                    R = int(parts[1])
                except ValueError:
                    return False
                if not (0 <= L <= R < K):
                    return False
                if R - L + 1 >= x:
                    cover_cnt = len(teams)
                else:
                    cover_set = set()
                    for t in range(L, R + 1):
                        r = t % x
                        cover_set.update(teams_by_r[r])
                    cover_cnt = len(cover_set)
                if cover_cnt >= R - L + 1:
                    return False
                if exp_lines is not None:
                    if exp_idx >= len(exp_lines):
                        return False
                    if exp_lines[exp_idx] != "NO":
                        return False
                    exp_idx += 1
                    if exp_idx >= len(exp_lines):
                        return False
                    exp_parts = exp_lines[exp_idx].split()
                    exp_idx += 1
                    if len(exp_parts) != 2:
                        return False
                    try:
                        exp_L = int(exp_parts[0])
                        exp_R = int(exp_parts[1])
                    except ValueError:
                        return False
                    if L != exp_L or R != exp_R:
                        return False
            else:
                return False

    if out_idx != len(out_lines):
        return False
    if exp_lines is not None and exp_idx != len(exp_lines):
        return False
    return True