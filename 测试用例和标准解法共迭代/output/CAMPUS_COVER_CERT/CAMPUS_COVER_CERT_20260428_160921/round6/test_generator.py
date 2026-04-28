def generate_tests():
    import random
    random.seed(0)
    tests = []

    def make_input(x, q, ops):
        lines = [f'{x} {q}']
        lines.extend(ops)
        return '\n'.join(lines) + '\n'

    # ------------------------------------------------------------
    # bucket: small_brute_force
    # ------------------------------------------------------------
    # 1. manual: x=3, team 0,2, query 2,3
    ops1 = ['1 0', '1 2', '2 2', '2 3']
    tests.append({
        'input': make_input(3, len(ops1), ops1),
        'source': 'small_brute_force',
        'purpose': '验证基本YES/NO',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 3, 'q': 4}
    })

    # 2. manual: x=4, team 0,0,0,1, query 4 -> NO conflict [3,3]
    ops2 = ['1 0']*3 + ['1 1'] + ['2 4']
    tests.append({
        'input': make_input(4, len(ops2), ops2),
        'source': 'small_brute_force',
        'purpose': '测试队伍数足够但仍因覆盖缺口导致NO',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 4, 'q': 5}
    })

    # 3. manual: x=5, team 0,0,1,1, query 4 -> NO conflict [2,3]
    ops3 = ['1 0', '1 0', '1 1', '1 1', '2 4']
    tests.append({
        'input': make_input(5, len(ops3), ops3),
        'source': 'small_brute_force',
        'purpose': '测试字典序最小冲突区间为[2,3]而非[3,3]',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 5, 'q': 5}
    })

    # 4. random small test 1
    def gen_random_test(x_lo, x_hi, q_lo, q_hi, k_lo, k_hi, max_total_k):
        x = random.randint(x_lo, x_hi)
        q = random.randint(q_lo, q_hi)
        ops = []
        total_k = 0
        teams = 0
        for _ in range(q):
            if teams == 0:
                r = random.random()
                if r < 0.9:
                    typ = 1
                else:
                    typ = 2
            else:
                if total_k >= max_total_k - k_lo:
                    typ = 1
                else:
                    if random.random() < 0.5:
                        typ = 1
                    else:
                        typ = 2
            if typ == 1:
                a = random.randint(0, 1000000000)
                ops.append(f'1 {a}')
                teams += 1
            else:
                max_k = min(k_hi, max_total_k - total_k)
                if max_k < k_lo:
                    a = random.randint(0, 1000000000)
                    ops.append(f'1 {a}')
                    teams += 1
                else:
                    K = random.randint(k_lo, max_k)
                    ops.append(f'2 {K}')
                    total_k += K
        return x, q, ops

    # random small 1: oracle range
    x4,q4,ops4 = gen_random_test(2,10,5,20,1,10,200)
    tests.append({
        'input': make_input(x4,q4,ops4),
        'source': 'small_brute_force',
        'purpose': '随机小测试',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': x4, 'q': q4}
    })

    # random small 2: oracle range
    x5,q5,ops5 = gen_random_test(2,10,10,30,1,5,200)
    tests.append({
        'input': make_input(x5,q5,ops5),
        'source': 'small_brute_force',
        'purpose': '随机小测试2',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': x5, 'q': q5}
    })

    # random small 3: oracle range
    x6,q6,ops6 = gen_random_test(2,10,5,50,1,10,200)
    tests.append({
        'input': make_input(x6,q6,ops6),
        'source': 'small_brute_force',
        'purpose': '随机小测试3',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': x6, 'q': q6}
    })

    # ------------------------------------------------------------
    # bucket: edge_cases
    # ------------------------------------------------------------
    # e1: x=1 always YES
    ops_e1 = ['1 0', '1 0', '1 0', '2 3', '2 1']
    tests.append({
        'input': make_input(1, len(ops_e1), ops_e1),
        'source': 'edge_cases',
        'purpose': 'x=1 全部YES',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 1, 'q': 5}
    })

    # e2: x=200 (oracle max) small random
    x_e2,q_e2,ops_e2 = gen_random_test(2,200,10,200,1,10,4000)
    tests.append({
        'input': make_input(x_e2,q_e2,ops_e2),
        'source': 'edge_cases',
        'purpose': 'x=200 oracle内随机',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': x_e2, 'q': q_e2}
    })

    # e3: x max 400k, few ops, large a_i
    ops_e3 = ['1 0', '1 1000000000', '2 1', '2 2', '2 3']
    tests.append({
        'input': make_input(400000, len(ops_e3), ops_e3),
        'source': 'edge_cases',
        'purpose': '极大x和边界a_i',
        'expect_oracle': False,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 400000, 'q': 5}
    })

    # e4: no team, query K=1
    ops_e4 = ['2 1']
    tests.append({
        'input': make_input(100, len(ops_e4), ops_e4),
        'source': 'edge_cases',
        'purpose': '无队伍查询，预期NO',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 100, 'q': 1}
    })

    # e5: large K (1e9) but few teams
    ops_e5 = ['1 0', '1 0', '1 0', '1 0', '1 0', '2 1000000000']
    tests.append({
        'input': make_input(100, len(ops_e5), ops_e5),
        'source': 'edge_cases',
        'purpose': 'K=1e9极大，应为NO',
        'expect_oracle': False,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 100, 'q': 6}
    })

    # e6: x=2, single team, query K=2
    ops_e6 = ['1 0', '2 2']
    tests.append({
        'input': make_input(2, len(ops_e6), ops_e6),
        'source': 'edge_cases',
        'purpose': 'x=2单队伍K=2，应YES',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 2, 'q': 2}
    })

    # e7: high a_i and x=400k
    ops_e7 = ['1 0', '1 1000000000', '2 2', '2 3']
    tests.append({
        'input': make_input(400000, len(ops_e7), ops_e7),
        'source': 'edge_cases',
        'purpose': '高边界a_i与x=400k',
        'expect_oracle': False,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 400000, 'q': 4}
    })

    # ------------------------------------------------------------
    # bucket: random_small
    # ------------------------------------------------------------
    # group1: oracle safe
    for i in range(3):
        x_r,q_r,ops_r = gen_random_test(2,200,10,200,1,50,10000)
        tests.append({
            'input': make_input(x_r,q_r,ops_r),
            'source': 'random_small',
            'purpose': '随机小测试(oracle内)',
            'expect_oracle': True,
            'is_sample': False,
            'is_large': False,
            'metadata': {'x': x_r, 'q': q_r}
        })

    # group2: larger params, expect_oracle=False
    for i in range(5):
        x_r,q_r,ops_r = gen_random_test(100,1000,50,1000,1,400,400000)
        tests.append({
            'input': make_input(x_r,q_r,ops_r),
            'source': 'random_small',
            'purpose': '随机中等测试(部分参数超oracle)',
            'expect_oracle': False,
            'is_sample': False,
            'is_large': False,
            'metadata': {'x': x_r, 'q': q_r}
        })

    # ------------------------------------------------------------
    # bucket: adversarial
    # ------------------------------------------------------------
    # adv1: Hall violation with a gap
    ops_adv1 = ['1 0', '1 2', '1 4', '1 4', '1 5', '2 5']
    tests.append({
        'input': make_input(6, len(ops_adv1), ops_adv1),
        'source': 'adversarial',
        'purpose': '构造覆盖缺口，验证字典序',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 6, 'q': 6}
    })

    ops_adv2 = ['1 0', '1 1', '1 3', '1 4', '1 6', '2 5']
    tests.append({
        'input': make_input(7, len(ops_adv2), ops_adv2),
        'source': 'adversarial',
        'purpose': '构造连续短缺，需正确输出最小冲突区间',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 7, 'q': 6}
    })

    # adv3: all a=0, query K=3 -> NO [2,2]
    ops_adv3 = ['1 0']*3 + ['2 3']
    tests.append({
        'input': make_input(3, len(ops_adv3), ops_adv3),
        'source': 'adversarial',
        'purpose': '全是a=0的队伍，K=3因缺覆盖2而NO',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 3, 'q': 4}
    })

    # adv4: variant of sample2
    ops_adv4 = ['1 0', '1 2', '1 2', '1 3', '2 4']
    tests.append({
        'input': make_input(5, len(ops_adv4), ops_adv4),
        'source': 'adversarial',
        'purpose': '类似样例2但调整参数',
        'expect_oracle': True,
        'is_sample': False,
        'is_large': False,
        'metadata': {'x': 5, 'q': 5}
    })

    # ------------------------------------------------------------
    # bucket: performance_max
    # ------------------------------------------------------------
    x_perf = 400000
    q_perf = 400000
    half = 200000
    ops_perf = []
    for _ in range(half):
        ops_perf.append('1 0')
    for _ in range(half):
        ops_perf.append('2 2')
    tests.append({
        'input': make_input(x_perf, q_perf, ops_perf),
        'source': 'performance_max',
        'purpose': '最大规模性能测试：x=400k,q=400k，全部YES且K总和=400k',
        'expect_oracle': False,
        'is_sample': False,
        'is_large': True,
        'metadata': {'x': x_perf, 'q': q_perf, 'total_K_yes': 400000}
    })

    return tests