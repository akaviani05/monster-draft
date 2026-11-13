// Public-information Monte Carlo player for Monster Draft Duel v1.
// No files, seed, referee state or opponent source are used by this program.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <string>
using namespace std;

namespace duel {
constexpr int TURNS = 30, STYLES = 5, SAMPLES = 2304;
struct Hand {
    int species[5]{}, strength[5]{}, cards[25]{}, size = 0, base = 0;
    void add(int c) {
        ++species[c / 5]; ++strength[c % 5]; ++cards[c];
        ++size; base += c % 5 + 1;
    }
};
struct State { Hand h[2]; array<int, 6> market{}; };
int banner, my_seat;
double banner_gain[31][31];
uint32_t random_state = 0x91e10da5;
uint32_t random32() {
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    return random_state ^= random_state << 5;
}
int player(int turn) { return ((turn % 4 == 1 || turn % 4 == 2) ? 1 : 0) ^ my_seat; }
int score(const State& s, int p) {
    const auto &a = s.h[p], &b = s.h[1-p];
    int total = a.base;
    bool spectrum = true;
    for (int k = 0; k < 5; ++k) {
        total += 9 * (a.species[k] >= 3);
        spectrum = spectrum && a.strength[k] > 0;
    }
    return total + 15 * spectrum + 12 * (a.species[0] > b.species[0])
        + 12 * (a.species[1] > b.species[1])
        + 9 * (a.strength[banner] > b.strength[banner]);
}
int winner(const State& s) {
    int difference = score(s, 0) - score(s, 1);
    if (!difference) difference = s.h[0].base - s.h[1].base;
    for (int k = 4; !difference && k >= 0; --k)
        difference = s.h[0].strength[k] - s.h[1].strength[k];
    return (difference > 0) - (difference < 0);
}
double utility(const State& s) {
    return 24 * winner(s) + clamp(score(s, 0)-score(s, 1), -40, 40);
}

// Policies never inspect the sampled future draw order. The first three match
// simple reference strategies; the fourth is a flexible opponent-aware policy.
array<double, 6> values(const State& s, int p, int turn, int style) {
    const auto &a = s.h[p], &b = s.h[1-p];
    array<double, 6> v{};
    int missing = 0;
    for (int k = 0; k < 5; ++k) missing += a.strength[k] == 0;
    int left = 15 - a.size;
    double sg[5]{}, kg[5]{};
    for (int k = 0; k < 5; ++k) {
        int n = a.species[k];
        if (style == 1) {
            const double squad[] = {2, 3, 8, 0};
            sg[k] = squad[min(n, 3)] + (k < 2 ? 1.5 : 0);
            kg[k] = (a.strength[k] ? 0 : 3.5) + (k == banner ? 1.2 : 0);
        } else if (style == 2) {
            const double squad[] = {2.1, 3.7, 8, 0};
            sg[k] = squad[min(n, 3)] + (b.species[k] == 2 ? 1.5 : 0);
            if (k < 2) sg[k] += abs(n - b.species[k]) <= 1 ? 3.1 : .6;
            kg[k] = (a.strength[k] ? 0 : 4);
            if (k == banner) kg[k] += abs(a.strength[k]-b.strength[k]) <= 1 ? 2.8 : .4;
        } else if (style == 3) {
            // Save flexibility early, then value actual bonus completion as
            // the remaining picks disappear. Never chase an impossible squad.
            if (n == 0 && left >= 3) sg[k] = 1.6;
            if (n == 1 && left >= 2) sg[k] = 3.0;
            if (n == 2) sg[k] = left <= 3 ? 9 : 6.3;
            if (!a.strength[k] && missing <= left)
                kg[k] = missing == 1 ? (left <= 3 ? 15 : 7.0) : 4.2;
            if (k < 2) sg[k] += banner_gain[29-turn][n-b.species[k]+15];
            if (k == banner)
                kg[k] += .75 * banner_gain[29-turn][a.strength[k]-b.strength[k]+15];
            // Denial matters most when an opponent can complete a bonus now.
            if (b.species[k] == 2) sg[k] += 1.4;
            if (!b.strength[k]) kg[k] += .45;
        }
    }
    for (int i = 0; i < 6; ++i) {
        int c = s.market[i];
        v[i] = c % 5 + 1 + sg[c/5] + kg[c%5];
        if (style == 4) v[i] = (s.market[0]/5 == 0 || s.market[0]%5 == 4) && i == 0 ? 100 : 0;
        // At the very last pick exact scoring and every tiebreak are available.
        if (turn == 29 && style == 3) {
            State next = s; next.h[p].add(c);
            v[i] = (p ? -1 : 1) * (1000 * winner(next) + score(next, 0) - score(next, 1));
        }
    }
    return v;
}
int policy(const State& s, int p, int turn, int style) {
    if (style == 4) {
        if (s.market[0]/5 == 0 || s.market[0]%5 == 4) return 0;
        return random32() % 6;
    }
    auto v = values(s, p, turn, style);
    return int(max_element(v.begin(), v.end()) - v.begin());
}

// At most three picks remain here. Enumerate every possible refill and allow
// our next choice to depend on that revealed card, without knowing later draws.
// The only opposing pick in this subtree is the final pick (the snake order).
double endgame(const State& s, array<int, 25>& remaining, int count, int turn,
               const array<double, STYLES>& weights) {
    int p = player(turn);
    double result = -1e30;
    double probabilities[6]{};
    if (p) {
        for (int style = 0; style < STYLES; ++style) {
            if (style == 4 && !(s.market[0]/5 == 0 || s.market[0]%5 == 4)) {
                for (double& probability : probabilities) probability += weights[style]/6;
            } else probabilities[policy(s, p, turn, style)] += weights[style];
        }
        result = 0;
    }
    for (int action = 0; action < 6; ++action) {
        if (p && !probabilities[action]) continue;
        State next = s; next.h[p].add(s.market[action]);
        double value = 0;
        if (turn == 29) value = utility(next);
        else for (int c = 0; c < 25; ++c) if (remaining[c]) {
            int copies = remaining[c]--;
            next.market[action] = c;
            value += double(copies)/count * endgame(next, remaining, count-1, turn+1, weights);
            ++remaining[c];
        }
        if (p) result += probabilities[action] * value;
        else result = max(result, value);
    }
    return result;
}

struct Bot {
    State state;
    array<double, STYLES> likelihood{{0, 0, 0, .7, -1}};
    void observe(int pick, int turn) {
        for (int style = 0; style < STYLES; ++style) {
            auto v = values(state, 1, turn, style);
            double best = *max_element(v.begin(), v.end()), sum = 0;
            for (double value : v) sum += exp((value-best)/.65);
            double probability = .97 * exp((v[pick]-best)/.65)/sum + .03/6;
            // A little forgetting permits the opponent to change strategy.
            likelihood[style] = .94 * likelihood[style] + log(probability);
        }
        state.h[1].add(state.market[pick]);
    }
    int choose(int turn) {
        if (turn == 29) return policy(state, 0, turn, 3);
        array<int, 50> unseen{};
        int count = 0;
        for (int c = 0; c < 25; ++c) {
            int copies = 2 - state.h[0].cards[c] - state.h[1].cards[c]
                - int(std::count(state.market.begin(), state.market.end(), c));
            for (int n = 0; n < copies; ++n) unseen[count++] = c;
        }
        // Exact finite-deck sampling, without replacement. Seed depends only
        // on public observations, so repeated games are reproducible.
        random_state = 0x91e10da5u + turn;
        for (int c : state.market) random_state = (random_state ^ (c+1)) * 16777619u;
        for (const auto& hand : state.h)
            for (int n : hand.cards) random_state = (random_state ^ (n+1)) * 16777619u;
        if (!random_state) random_state = 1;
        array<double, STYLES> weights{};
        double maximum = *max_element(likelihood.begin(), likelihood.end()), sum = 0;
        for (int k = 0; k < STYLES; ++k) sum += weights[k] = exp(likelihood[k]-maximum);
        for (double& weight : weights) weight = .9*weight/sum + .1/STYLES;
        if (turn >= 27) {
            array<int, 25> remaining{};
            for (int i = 0; i < count; ++i) ++remaining[unseen[i]];
            double best_value = -1e30;
            int best = 0;
            for (int action = 0; action < 6; ++action) {
                State next = state; next.h[0].add(next.market[action]);
                double value = 0;
                for (int c = 0; c < 25; ++c) if (remaining[c]) {
                    int copies = remaining[c]--;
                    next.market[action] = c;
                    value += double(copies)/count * endgame(next, remaining, count-1, turn+1, weights);
                    ++remaining[c];
                }
                if (value > best_value) { best_value = value; best = action; }
            }
            return best;
        }
        double outcomes[6]{};
        for (int sample = 0; sample < SAMPLES; ++sample) {
            auto draws = unseen;
            for (int j = 0; j < 30-turn; ++j)
                swap(draws[j], draws[j + random32() % (count-j)]);
            double u = double(random32()) / 4294967296.0;
            int style = 0;
            while (style < STYLES-1 && (u -= weights[style]) > 0) ++style;
            // Common worlds (and random policy choices) reduce the variance
            // between root moves, rather than comparing unrelated shuffles.
            uint32_t rollout_seed = random32();
            for (int action = 0; action < 6; ++action) {
                if (find(state.market.begin(), state.market.begin()+action, state.market[action])
                    != state.market.begin()+action) continue;
                random_state = rollout_seed;
                State trial = state;
                trial.h[0].add(trial.market[action]);
                trial.market[action] = draws[0];
                for (int t = turn+1; t < TURNS; ++t) {
                    int p = player(t);
                    int pick = policy(trial, p, t, p ? style : 3);
                    trial.h[p].add(trial.market[pick]);
                    trial.market[pick] = draws[t-turn];
                }
                // Optimize winning, with a smooth margin term to distinguish
                // equally successful moves and reduce sampling brittleness.
                outcomes[action] += utility(trial);
            }
            random_state = rollout_seed;
        }
        auto heuristic = values(state, 0, turn, 3);
        for (int i = 1; i < 6; ++i)
            for (int j = 0; j < i; ++j)
                if (state.market[i] == state.market[j]) { outcomes[i] = outcomes[j]; break; }
        int best = 0;
        for (int i = 1; i < 6; ++i)
            if (outcomes[i] + .001*heuristic[i] > outcomes[best] + .001*heuristic[best]) best = i;
        return best;
    }
};
void initialize() {
    for (int left = 0; left <= 30; ++left) {
        double scale = .65 + .45 * sqrt(left);
        for (int d = -15; d <= 15; ++d) {
            auto potential = [&](int lead) { return left ? tanh(lead / scale) : double((lead > 0)-(lead < 0)); };
            banner_gain[left][d+15] = 12 * (potential(d+1) - potential(d));
        }
    }
}
} // namespace duel

#ifndef CHAMPION_TEST
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    using namespace duel;
    if (!(cin >> banner)) return 0;
    --banner; initialize(); Bot bot;
    for (int turn = 0; turn < TURNS; ++turn) {
        string header, card;
        if (!(cin >> header)) return 0;
        if (turn == 0) my_seat = header == "YOURTURN" ? 0 : 1;
        for (int& c : bot.state.market) {
            if (!(cin >> card)) return 0;
            c = (card[0]-'A')*5 + card[1]-'1';
        }
        int pick;
        if (header == "YOURTURN") {
            pick = bot.choose(turn);
            cout << pick << endl;
            bot.state.h[0].add(bot.state.market[pick]);
        } else {
            if (!(cin >> pick)) return 0;
            bot.observe(pick, turn);
        }
    }
}
#endif
