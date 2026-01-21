class CoupPlayer:
    def __init__(self, name):
        self.name = name
        self.coins = 2
        self.cards = [-2, -2]
        self.numCards = 2
        self.isAlive = True

    def die(self):
        self.isAlive = False

    def lose_card(self, card_index):
        # card_index is 0 or 1, indicating which card position to lose
        # replace the card with the "dead" card
        if card_index < 0 or card_index >= len(self.cards):
            # Invalid index, lose first available card
            if self.cards[0] != -2:
                card_index = 0
            elif self.cards[1] != -2:
                card_index = 1
            else:
                # Both cards already lost, shouldn't happen
                return -2
        
        lost_card_value = self.cards[card_index]
        self.cards[card_index] = -2
        self.numCards -= 1
        
        #check if player is alive
        if(self.numCards <= 0):
            self.die()

        return lost_card_value
    
    def getActions(self):
        if self.coins < 3:
            return([0, 2, 3, 5, 6])
        elif self.coins < 7:
            return([0, 1, 2, 3, 5, 6])
        elif self.coins < 10:
            return([0, 1, 2, 3, 5, 6, 7])
        else:
            return([7])

    
        




