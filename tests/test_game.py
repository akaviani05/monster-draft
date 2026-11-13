from collections import Counter
import unittest
from unittest.mock import patch
from runner.game import active_seat, deck, result, score, setup, simulate
from arena.scheduling import round_robin


class RulesTests(unittest.TestCase):
    def test_inventory(self):
        self.assertEqual(len(deck()), 50)
        self.assertEqual(set(Counter(deck()).values()), {2})
        self.assertEqual(len(Counter(deck())), 25)

    def test_snake_and_final_inventory(self):
        self.assertEqual([active_seat(i) for i in range(10)], [0,1,1,0,0,1,1,0,0,1])
        self.assertEqual(Counter(active_seat(i) for i in range(30)), {0:15,1:15})
        for seed in range(100):
            log = simulate(seed, [lambda *_:0]*2)
            self.assertEqual(list(map(len,log['hands'])), [15,15])
            observed = log['initial_market'] + [t['refill'] for t in log['turns']]
            self.assertTrue(all(n<=2 for n in Counter(observed).values()))

    def test_determinism_and_uniform_banner_support(self):
        self.assertEqual(setup(123), setup(123))
        counts = Counter(setup(seed)[0] for seed in range(2000))
        self.assertEqual(set(counts), {1,2,3,4,5})
        self.assertTrue(all(300<n<500 for n in counts.values()))

    def test_fixed_slots(self):
        log = simulate(42, [lambda *_:2]*2)
        for before, after in zip(log['turns'], log['turns'][1:]):
            self.assertEqual(after['market'][2],before['refill'])
            for i in (0,1,3,4,5): self.assertEqual(before['market'][i],after['market'][i])

    def test_known_score(self):
        a = 'A5 A4 A2 A1 B5 B4 B3 C5 C2 C1 D4 D3 D1 E5 E2'.split()
        b = 'A5 A3 A2 B5 B4 B1 B2 C5 C3 C2 D5 D4 D2 E4 E3'.split()
        self.assertEqual(score(a,b,2)['total'],110)
        self.assertEqual(score(b,a,2)['total'],122)
        self.assertEqual(result([a,b],2)['winner'],1)

    def test_squads_only_once(self):
        self.assertEqual(score(['C1']*6,[],2)['squads'],9)
        self.assertEqual(score(['C1']*2,[],2)['squads'],0)

    def test_spectrum_and_equal_banners(self):
        hand = ['A1','A2','B3','D4','E5']
        s=score(hand,hand,2)
        self.assertEqual(s['spectrum'],15)
        self.assertEqual(s['banner_a']+s['banner_b']+s['banner_strength'],0)
        self.assertEqual(score(hand[:-1],[],2)['spectrum'],0)

    def test_draw(self):
        self.assertIsNone(result([['A1','B5'],['A1','B5']],3)['winner'])

    def test_tiebreak_base_then_descending_strength(self):
        with patch('runner.game.score', return_value={'total':100,'base':20}):
            self.assertEqual(result([['A5','A1'],['B4','B2']],1)['winner'],0)
        with patch('runner.game.score', side_effect=[{'total':100,'base':21},{'total':100,'base':20}]):
            self.assertEqual(result([['A1'],['B5']],1)['winner'],0)

    def test_invalid_policy(self):
        for choice in (-1,6,True,'2'):
            with self.assertRaises(ValueError):simulate(0,[lambda *_,c=choice:c]*2)


class ScheduleTests(unittest.TestCase):
    def test_all_pairs_once_and_balanced_seats(self):
        for n in range(2,52):
            rounds=round_robin(range(n));pairs=set();first=Counter();counts=Counter()
            for matches in rounds:
                occupied=[]
                for a,b in matches:
                    pair=tuple(sorted((a,b)))
                    self.assertNotIn(pair,pairs);pairs.add(pair)
                    first[a]+=1;occupied += [a,b];counts[a]+=1;counts[b]+=1
                self.assertEqual(len(occupied),len(set(occupied)))
            self.assertEqual(len(pairs),n*(n-1)//2)
            self.assertTrue(all(counts[t]==n-1 for t in range(n)))
            self.assertLessEqual(max(first[t] for t in range(n))-min(first[t] for t in range(n)),1)

    def test_empty(self):
        self.assertEqual(round_robin([]),[])
        self.assertEqual(round_robin([1]),[])
