import random
from typing import List, Dict, Optional
import discord

# --- CONSTANTS & DATA ---

ENVIRONMENTS = {
    "Urban": {
        "icon": "🏙️",
        "hazards": [
            {"name": "Crowded Market", "check": "DEX", "difficulty": "Regular", "desc": "A dense crowd blocks your path."},
            {"name": "Locked Gate", "check": "STR", "difficulty": "Hard", "desc": "A tall iron gate creates a dead end."},
            {"name": "Slippery Cobbles", "check": "DEX", "difficulty": "Regular", "desc": "Rain-slicked stones make footing treacherous."},
            {"name": "Police Barricade", "check": "Luck", "difficulty": "Regular", "desc": "Officers are blocking the street."},
            {"name": "Fruit Cart", "check": "DEX", "difficulty": "Regular", "desc": "The classic obstacle! My cabbages!"},
            {"name": "Narrow Alley", "check": "SIZ", "difficulty": "Regular", "desc": "It's a tight squeeze."},
            {"name": "Construction Site", "check": "DEX", "difficulty": "Regular", "desc": "Open pits and scaffolding."},
        ]
    },
    "Wilderness": {
        "icon": "🌲",
        "hazards": [
            {"name": "Fallen Tree", "check": "STR", "difficulty": "Regular", "desc": "A massive oak blocks the trail."},
            {"name": "Mudslide", "check": "DEX", "difficulty": "Hard", "desc": "The ground gives way beneath you."},
            {"name": "Dense Thicket", "check": "STR", "difficulty": "Regular", "desc": "Thorny vines tear at your clothes."},
            {"name": "Stream", "check": "DEX", "difficulty": "Regular", "desc": "A rushing stream cuts across the path."},
            {"name": "Wild Animal", "check": "DEX", "difficulty": "Regular", "desc": "A bear? A wolf? Run!"},
            {"name": "Steep Incline", "check": "CON", "difficulty": "Regular", "desc": "A grueling uphill sprint."},
        ]
    },
    "Driving": {
        "icon": "🚗",
        "hazards": [
            {"name": "Red Light", "check": "Drive Auto", "difficulty": "Regular", "desc": "Traffic from the cross street is coming!"},
            {"name": "Pedestrian", "check": "Drive Auto", "difficulty": "Hard", "desc": "Someone steps out into the road!"},
            {"name": "Sharp Turn", "check": "Drive Auto", "difficulty": "Regular", "desc": "A hairpin bend approaches."},
            {"name": "Road Works", "check": "Drive Auto", "difficulty": "Regular", "desc": "Lane closure ahead."},
            {"name": "Oil Slick", "check": "Drive Auto", "difficulty": "Hard", "desc": "Slippery road surface."},
            {"name": "Oncoming Traffic", "check": "Drive Auto", "difficulty": "Hard", "desc": "You swerve into the wrong lane!"},
        ]
    }
}

# --- CLASSES ---

class ChaseLocation:
    def __init__(self, index, environment_type):
        self.index = index
        self.environment = environment_type
        self.hazard = None
        self.description = "Clear path"
        self.generate_hazard()

    def generate_hazard(self):
        # 30% chance of hazard, but index 0 is always clear
        if self.index > 0 and random.random() < 0.3:
            env_data = ENVIRONMENTS.get(self.environment, ENVIRONMENTS["Urban"])
            hazard_data = random.choice(env_data["hazards"])
            self.hazard = hazard_data
            self.description = f"⚠️ **{hazard_data['name']}** ({hazard_data['check']} Check)"
        else:
            self.hazard = None
            self.description = "Clear path"

    def to_dict(self):
        return {
            "index": self.index,
            "environment": self.environment,
            "hazard": self.hazard,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data):
        loc = cls(data["index"], data["environment"])
        loc.hazard = data["hazard"]
        loc.description = data["description"]
        return loc

class ChaseParticipant:
    def __init__(self, user_id, name, is_npc=False):
        self.user_id = str(user_id)
        self.name = name
        self.is_npc = is_npc
        self.position = 0
        self.mov = 8
        self.dex = 50
        self.str = 50
        self.con = 50
        self.drive = 20
        self.actions_remaining = 0
        self.move_actions_remaining = 0
        self.state = "active" # active, caught, escaped

    def set_stats(self, stats):
        self.mov = stats.get("MOV", 8)
        self.dex = stats.get("DEX", 50)
        self.str = stats.get("STR", 50)
        self.con = stats.get("CON", 50)
        self.drive = stats.get("Drive Auto", 20)

    def reset_round_actions(self):
        # Base: 1 Standard Action + 1 Move Action
        self.actions_remaining = 1
        self.move_actions_remaining = 1

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "name": self.name,
            "is_npc": self.is_npc,
            "position": self.position,
            "mov": self.mov,
            "dex": self.dex,
            "str": self.str,
            "con": self.con,
            "drive": self.drive,
            "actions_remaining": self.actions_remaining,
            "move_actions_remaining": self.move_actions_remaining,
            "state": self.state
        }

    @classmethod
    def from_dict(cls, data):
        p = cls(data["user_id"], data["name"], data["is_npc"])
        p.position = data["position"]
        p.mov = data["mov"]
        p.dex = data["dex"]
        p.str = data["str"]
        p.con = data["con"]
        p.drive = data["drive"]
        p.actions_remaining = data["actions_remaining"]
        p.move_actions_remaining = data["move_actions_remaining"]
        p.state = data["state"]
        return p

class ChaseSession:
    def __init__(self, guild_id, channel_id, environment="Urban", mode="Foot"):
        self.guild_id = str(guild_id)
        self.channel_id = str(channel_id)
        self.environment = environment
        self.mode = mode
        self.track = []
        self.participants = []
        self.turn_order = []
        self.current_turn_index = 0
        self.round_number = 1
        self.log = []
        self.message_id = None # Store dashboard message ID

        # Generate initial track (5 locations)
        for i in range(5):
            self.track.append(ChaseLocation(i, self.environment))
        self.track[0].hazard = None
        self.track[0].description = "Start Line"

    def add_log(self, message):
        self.log.append(message)
        if len(self.log) > 5:
            self.log.pop(0)

    def get_participant(self, user_id):
        for p in self.participants:
            if p.user_id == str(user_id):
                return p
        return None

    def sort_turn_order(self):
        self.participants.sort(key=lambda p: p.dex, reverse=True)
        self.turn_order = [p.user_id for p in self.participants]

    def next_round(self):
        self.round_number += 1
        self.current_turn_index = 0
        for p in self.participants:
            p.reset_round_actions()
        self.add_log(f"🔄 **Round {self.round_number} Start!**")

    def ensure_track_length(self, target_index):
        while len(self.track) <= target_index + 2:
            next_idx = len(self.track)
            self.track.append(ChaseLocation(next_idx, self.environment))

    def to_dict(self):
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "environment": self.environment,
            "mode": self.mode,
            "track": [t.to_dict() for t in self.track],
            "participants": [p.to_dict() for p in self.participants],
            "turn_order": self.turn_order,
            "current_turn_index": self.current_turn_index,
            "round_number": self.round_number,
            "log": self.log,
            "message_id": self.message_id
        }

    @classmethod
    def from_dict(cls, data):
        s = cls(data["guild_id"], data["channel_id"], data["environment"], data.get("mode", "Foot"))
        s.track = [ChaseLocation.from_dict(t) for t in data["track"]]
        s.participants = [ChaseParticipant.from_dict(p) for p in data["participants"]]
        s.turn_order = data["turn_order"]
        s.current_turn_index = data["current_turn_index"]
        s.round_number = data["round_number"]
        s.log = data.get("log", [])
        s.message_id = data.get("message_id")
        return s

class ChaseService:
    def __init__(self):
        self.sessions = {} # guild_id -> channel_id -> ChaseSession

    def get_session(self, guild_id, channel_id) -> Optional[ChaseSession]:
        return self.sessions.get(str(guild_id), {}).get(str(channel_id))

    def create_session(self, guild_id, channel_id, environment="Urban", mode="Foot") -> ChaseSession:
        session = ChaseSession(guild_id, channel_id, environment, mode)
        if str(guild_id) not in self.sessions:
            self.sessions[str(guild_id)] = {}
        self.sessions[str(guild_id)][str(channel_id)] = session
        return session

    def remove_session(self, guild_id, channel_id):
        if str(guild_id) in self.sessions:
            if str(channel_id) in self.sessions[str(guild_id)]:
                del self.sessions[str(guild_id)][str(channel_id)]

    def load_sessions(self, all_data: Dict):
        for guild_id, guild_data in all_data.items():
            if guild_id not in self.sessions: self.sessions[guild_id] = {}
            for channel_id, session_data in guild_data.items():
                try:
                    if "track" not in session_data: continue
                    session = ChaseSession.from_dict(session_data)
                    self.sessions[guild_id][channel_id] = session
                except:
                    pass

    def get_all_sessions_dict(self) -> Dict:
        all_data = {}
        for guild_id, guild_sessions in self.sessions.items():
            all_data[guild_id] = {cid: s.to_dict() for cid, s in guild_sessions.items()}
        return all_data

    @staticmethod
    def create_dashboard_embed(session: ChaseSession):
        env_icon = ENVIRONMENTS.get(session.environment, {}).get("icon", "🏃")
        
        embed = discord.Embed(
            title=f"{env_icon} Chase Dashboard: Round {session.round_number}",
            description=f"**Environment:** {session.environment} | **Mode:** {session.mode}",
            color=discord.Color.dark_red()
        )

        positions = [p.position for p in session.participants]
        if not positions: positions = [0]
        min_pos = min(positions)
        max_pos = max(positions) + 2
        
        session.ensure_track_length(max_pos)

        start_idx = max(0, min_pos - 1)
        end_idx = max_pos

        track_str = ""
        for i in range(start_idx, end_idx + 1):
            if i >= len(session.track): break
            loc = session.track[i]

            parts_here = [p for p in session.participants if p.position == i]

            loc_icon = "🟩"
            if loc.hazard: loc_icon = "⚠️"

            line = f"`{i:02}` {loc_icon} "
            if parts_here:
                avatars = " ".join([("👹" if p.is_npc else "🕵️") for p in parts_here])
                line += f"**{avatars}**"

            if loc.hazard:
                line += f" *{loc.hazard['name']} ({loc.hazard['check']})*"
            elif parts_here:
                line += " *Clear*"
            
            track_str += line + "\n"
            if i < end_idx:
                track_str += "      |\n"

        if not track_str: track_str = "Empty Track"
        embed.add_field(name="🏁 The Track", value=track_str, inline=False)

        status_str = ""
        for p in session.participants:
            actions = "🔴" * p.actions_remaining + "⚪" * (1-p.actions_remaining)
            moves = "🦶" * p.move_actions_remaining
            status_str += f"**{p.name}** (Pos {p.position}): {actions} {moves} [MOV {p.mov}]\n"

        embed.add_field(name="👥 Participants", value=status_str or "No participants", inline=False)

        log_str = "\n".join(session.log[-5:])
        if log_str:
            embed.add_field(name="📜 Log", value=log_str, inline=False)

        embed.set_footer(text="Chase Tracker")
        return embed
