def check(input_str: str, output_str: str, expected_str: str | None = None) -> bool:
    try:
        in_tokens = input_str.split()
        if not in_tokens:
            return False
        it_in = iter(in_tokens)
        x = int(next(it_in))
        q = int(next(it_in))

        teams = []
        ops = []
        for _ in range(q):
            t = int(next(it_in))
            val = int(next(it_in))
            ops.append((t, val))
            if t == 1:
                teams.append((len(teams) + 1, val))

        out_tokens = output_str.split()
        it_out = iter(out_tokens)

        for t, val in ops:
            if t == 2:
                K = val
                try:
                    res = next(it_out)
                except StopIteration:
                    return False
                if res == "YES":
                    used_ids = set()
                    used_slots = set()
                    for _ in range(K):
                        tid = int(next(it_out))
                        s = int(next(it_out))
                        if not (0 <= s < K):
                            return False
                        if tid in used_ids or s in used_slots:
                            return False
                        used_ids.add(tid)
                        used_slots.add(s)
                        a = None
                        for tid_t, a_t in teams:
                            if tid_t == tid:
                                a = a_t
                                break
                        if a is None:
                            return False
                        if not (s % x == a % x or s % x == (a + 1) % x):
                            return False
                elif res == "NO":
                    L = int(next(it_out))
                    R = int(next(it_out))
                    if not (0 <= L <= R < K):
                        return False
                    cnt = 0
                    length = R - L + 1
                    if length >= x:
                        cnt = len(teams)
                    else:
                        l_mod = L % x
                        r_mod = R % x
                        for _, a_t in teams:
                            r1 = a_t % x
                            r2 = (a_t + 1) % x
                            def in_range(r, l, r_r):
                                if l <= r_r:
                                    return l <= r <= r_r
                                return r >= l or r <= r_r
                            if in_range(r1, l_mod, r_mod) or in_range(r2, l_mod, r_mod):
                                cnt += 1
                    if cnt >= length:
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