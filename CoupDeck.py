import random

class CoupDeck:
    def __init__(self):
        self.deck = [0,1,2,3,4]*3
        random.shuffle(self.deck)

    def shuffle(self):
        random.shuffle(self.deck)

    def draw(self):
        return self.deck.pop()

    def add(self, card1, card2 = -1):
        """Add card(s) back to deck. card2 is optional, -1 means don't add second card."""
        if card1 >= 0:  # Only add valid cards (0-4)
            self.deck.append(card1)
        if card2 >= 0:  # Only add if card2 is a valid card (0-4), not -1
            self.deck.append(card2)
        random.shuffle(self.deck)