def check(input_str: str, output_str: str, expected_str: str | None) -> bool:
    try:
        in_tokens = input_str.split()
        out_tokens = output_str.split()
        if not in_tokens or not out_tokens:
            return False
        it_in = iter(in_tokens)
        x = int(next(it_in))
        q = int(next(it_in))
        
        teams = []  # (id, a)
        it_out = iter(out_tokens)
        
        for _ in range(q):
            t = int(next(it_in))
            v = int(next(it_in))
            if t == 1:
                teams.append((len(teams) + 1, v))
            elif t == 2:
                K = v
                try:
                    res = next(it_out)
                except StopIteration:
                    return False
                
                if res == "YES":
                    ids = []
                    slots = []
                    for _ in range(K):
                        tid = int(next(it_out))
                        s = int(next(it_out))
                        ids.append(tid)
                        slots.append(s)
                    if len(ids) != K or len(slots) != K:
                        return False
                    if len(set(ids)) != K or len(set(slots)) != K:
                        return False
                    if any(not (0 <= s < K) for s in slots):
                        return False
                    team_map = {tid: a for tid, a in teams}
                    for tid, s in zip(ids, slots):
                        if tid not in team_map:
                            return False
                        a = team_map[tid]
                        r1 = a % x
                        r2 = (a + 1) % x
                        if not (s % x == r1 or s % x == r2):
                            return False
                elif res == "NO":
                    L = int(next(it_out))
                    R = int(next(it_out))
                    if not (0 <= L <= R < K):
                        return False
                    
                    # Count teams covering [L, R]
                    count = 0
                    for _, a in teams:
                        r1 = a % x
                        r2 = (a + 1) % x
                        covers = False
                        for r in (r1, r2):
                            rem = L % x
                            diff = (r - rem + x) % x
                            if L + diff <= R:
                                covers = True
                                break
                        if covers:
                            count += 1
                    
                    if count >= R - L + 1:
                        return False
                    
                    # Bounded minimality check to prevent TLE on large K/x
                    limit_l = min(L, 500)
                    for l in range(limit_l + 1):
                        max_r = R if l == L else min(l + x, K - 1)
                        for r in range(l, max_r + 1):
                            cnt = 0
                            for _, a in teams:
                                r1 = a % x
                                r2 = (a + 1) % x
                                covers = False
                                for rr in (r1, r2):
                                    rem = l % x
                                    diff = (rr - rem + x) % x
                                    if l + diff <= r:
                                        covers = True
                                        break
                                if covers:
                                    cnt += 1
                            if cnt < r - l + 1:
                                return False
                else:
                    return False
        try:
            next(it_out)
            return False
        except StopIteration:
            return True
    except Exception:
        return False