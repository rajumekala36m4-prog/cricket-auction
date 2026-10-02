# Initialize teams with their total budgets
teams = {
    "Team A": {"budget": 5000, "players": 0},
    "Team B": {"budget": 5000, "players": 0},
    "Team C": {"budget": 5000, "players": 0},
    "Team D": {"budget": 5000, "players": 0},
    "Team E": {"budget": 5000, "players": 0},
}

# Function to conduct bidding for a player
def conduct_auction(player_name, player_bid):
    global teams

    print(f"\nAuctioning Player: {player_name}")
    print(f"Base Bid: {player_bid}")

    if player_bid < 100:
        print("Error: Minimum bid amount is 100.")
        return

    winning_team = None

    for team_name, team_info in teams.items():
        if team_info["budget"] >= player_bid:
            bid_choice = input(f"{team_name}, do you want to bid for {player_name}? (y/n): ").lower()
            if bid_choice == "y":
                winning_team = team_name
                break

    if winning_team:
        teams[winning_team]["budget"] -= player_bid
        teams[winning_team]["players"] += 1
        print(f"{winning_team} bought {player_name} for {player_bid}.")
    else:
        print(f"No team could afford {player_name}. Player remains unsold.")

# Function to display the current status
def display_status():
    print("\nCurrent Team Status:")
    for team_name, team_info in teams.items():
        print(f"{team_name} - Players: {team_info['players']}, Remaining Budget: {team_info['budget']}")

# Function to validate team requirements
def validate_teams():
    print("\nValidating team requirements...")
    for team_name, team_info in teams.items():
        if team_info["players"] < 16:
            print(f"{team_name} needs to buy {16 - team_info['players']} more players.")
        else:
            print(f"{team_name} meets the requirement of 16 players.")

# Main auction loop
print("Welcome to the Cricket Auction!")
while True:
    action = input("\nEnter 'p' to auction a player, 's' to display status, or 'q' to quit: ").lower()
    if action == "p":
        player_name = input("Enter player's name: ")
        player_bid = int(input("Enter player's bid amount: "))
        conduct_auction(player_name, player_bid)
    elif action == "s":
        display_status()
    elif action == "q":
        break
    else:
        print("Invalid input. Please try again.")

# Final status and validation
display_status()
validate_teams()

print("\nAuction complete!")