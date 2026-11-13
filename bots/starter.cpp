#include <array>
#include <iostream>
#include <random>
#include <string>
using namespace std;

int main() {
    const int TURNS = 30;
    int banner;
    cin >> banner;
    mt19937 rng(random_device{}());
    uniform_int_distribution<int> random_slot(0, 5);
    for (int i = 0; i < TURNS; ++i) {
        string header;
        if (!(cin >> header)) return 0;
        array<string, 6> A;
        for (int j = 0; j < 6; ++j) cin >> A[j];
        if (header == "YOURTURN") {
            int choice;
            if (A[0][0] == 'A' || A[0][1] == '5') choice = 0;
            else choice = random_slot(rng);
            cout << choice << endl;
        } else {
            int opponent_choice;
            cin >> opponent_choice;
        }
    }
}
