# -*- coding: utf-8 -*-
"""
デュエルマスターズ風カードゲーム
"""

import random
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'duel-masters-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# ルーム管理
rooms = {}
player_rooms = {}

# カードデータベース（システム対応済み・カードは空）
# 実装可能なシステム：
# - 単色・多色カード対応 (civ: ["fire"] or ["fire", "darkness"])
# - S・トリガー (shield_trigger: True)
# - W・ブレイカー、T・ブレイカー (breaker: 2 or 3)
# - スピードアタッカー (ability に "スピードアタッカー" を含める)
# - ブロッカー (ability に "ブロッカー" を含める)
# - 召喚時効果 (ability に "バトルゾーンに出た時" を含める)
# - マナブースト (ability に "山札の上から○枚をマナゾーンに置く" を含める)
# - ドロー効果 (ability に "カードを○枚引く" を含める)
# - 除去効果 (ability に "クリーチャーを○体破壊する" を含める)
# - タップ効果 (ability に "クリーチャーを○体タップする" を含める)
# - 墓地回収 (ability に "墓地から" を含める)
# - ハンデス (ability に "手札を見て" を含める)
CARD_DB = [
    # ここにカードを追加してください
]

class DuelMastersGame:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.players = {
            "p1": {
                "deck": [],
                "hand": [],
                "mana": [],
                "battle_zone": [],
                "shields": 5,
                "shield_cards": [],
                "graveyard": [],
                "ready": False
            },
            "p2": {
                "deck": [],
                "hand": [],
                "mana": [],
                "battle_zone": [],
                "shields": 5,
                "shield_cards": [],
                "graveyard": [],
                "ready": False
            }
        }
        self.turn = "p1"
        self.turn_count = 1
        self.phase = "draw"  # draw, mana, main, attack, end
        self.winner = None
        self.log = ["デュエルマスターズ開始！"]
        self.attacking_creature = None
        self.attack_target = None
    
    def build_deck(self, player):
        """デッキを構築（各カード1-2枚で40枚デッキ）"""
        deck = []
        # 主要カードは2枚、サポートカードは1枚
        for card in CARD_DB:
            deck.append(dict(card))
            if card["cost"] <= 4:  # コスト4以下は2枚
                deck.append(dict(card))
        random.shuffle(deck)
        self.players[player]["deck"] = deck[:40]  # 40枚に調整
    
    def draw_card(self, player, count=1):
        """カードを引く"""
        for _ in range(count):
            if len(self.players[player]["deck"]) > 0:
                card = self.players[player]["deck"].pop(0)
                self.players[player]["hand"].append(card)
                self.log.append(f"{player}がカードを1枚引いた")
            else:
                self.winner = "p2" if player == "p1" else "p1"
                self.log.append(f"{player}のデッキ切れ！")
    
    def setup_shields(self, player):
        """シールドを5枚セット"""
        self.players[player]["shield_cards"] = []
        for _ in range(5):
            if len(self.players[player]["deck"]) > 0:
                shield_card = self.players[player]["deck"].pop(0)
                self.players[player]["shield_cards"].append(shield_card)
    
    def charge_mana(self, player, card_id):
        """手札からマナゾーンにカードをチャージ"""
        hand = self.players[player]["hand"]
        for i, card in enumerate(hand):
            if card["id"] == card_id:
                mana_card = hand.pop(i)
                mana_card["tapped"] = False
                # 文明情報を保持（配列の場合は最初の文明を使用）
                if isinstance(mana_card.get("civ"), list):
                    mana_card["civ_display"] = mana_card["civ"][0]
                else:
                    mana_card["civ_display"] = mana_card.get("civ", "fire")
                self.players[player]["mana"].append(mana_card)
                self.log.append(f"{player}が{mana_card['name']}をマナゾーンに置いた")
                return True
        return False
    
    def summon_creature(self, player, card_id):
        """クリーチャーを召喚"""
        hand = self.players[player]["hand"]
        for i, card in enumerate(hand):
            if card["id"] == card_id:
                # コストチェック
                available_mana = [m for m in self.players[player]["mana"] if not m.get("tapped", False)]
                if len(available_mana) < card["cost"]:
                    return False, "マナが足りません"
                
                # マナをタップ
                for j in range(card["cost"]):
                    available_mana[j]["tapped"] = True
                
                # 召喚
                creature = hand.pop(i)
                creature["summoning_sick"] = True
                creature["tapped"] = False
                self.players[player]["battle_zone"].append(creature)
                self.log.append(f"{player}が{creature['name']}を召喚した")
                
                # 能力処理
                self.trigger_ability(player, creature)
                return True, "召喚成功"
        return False, "カードが見つかりません"
    
    def cast_spell(self, player, card_id):
        """呪文を唱える"""
        hand = self.players[player]["hand"]
        for i, card in enumerate(hand):
            if card["id"] == card_id and card["type"] == "spell":
                # コストチェック
                available_mana = [m for m in self.players[player]["mana"] if not m.get("tapped", False)]
                if len(available_mana) < card["cost"]:
                    return False, "マナが足りません"
                
                # マナをタップ
                for j in range(card["cost"]):
                    available_mana[j]["tapped"] = True
                
                # 呪文を唱える
                spell = hand.pop(i)
                self.players[player]["graveyard"].append(spell)
                self.log.append(f"{player}が{spell['name']}を唱えた")
                
                # 効果処理（簡易版）
                self.process_spell_effect(player, spell)
                return True, "呪文発動"
        return False, "呪文が見つかりません"
    
    def trigger_ability(self, player, creature):
        """能力発動処理"""
        ability = creature.get("ability", "")
        opponent = "p2" if player == "p1" else "p1"
        
        # ドロー効果
        if "カードを3枚引く" in ability:
            self.draw_card(player, 3)
        elif "カードを2枚引く" in ability:
            self.draw_card(player, 2)
        elif "カードを1枚引く" in ability:
            self.draw_card(player, 1)
        
        # マナブースト
        if "自分の山札の上から5枚をマナゾーンに置く" in ability:
            for _ in range(5):
                if len(self.players[player]["deck"]) > 0:
                    mana_card = self.players[player]["deck"].pop(0)
                    mana_card["tapped"] = False
                    self.players[player]["mana"].append(mana_card)
            self.log.append("マナブースト！5枚マナに置いた")
        elif "自分の山札の上から1枚をマナゾーンに置く" in ability:
            if len(self.players[player]["deck"]) > 0:
                mana_card = self.players[player]["deck"].pop(0)
                mana_card["tapped"] = False
                self.players[player]["mana"].append(mana_card)
        
        # 除去効果
        if "相手のクリーチャーを2体まで破壊する" in ability:
            destroyed_count = 0
            for _ in range(2):
                if len(self.players[opponent]["battle_zone"]) > 0:
                    destroyed = self.players[opponent]["battle_zone"].pop(0)
                    self.players[opponent]["graveyard"].append(destroyed)
                    destroyed_count += 1
            if destroyed_count > 0:
                self.log.append(f"召喚時能力で{destroyed_count}体破壊した")
        elif "相手のクリーチャーを全て破壊する" in ability:
            destroyed_count = len(self.players[opponent]["battle_zone"])
            self.players[opponent]["graveyard"].extend(self.players[opponent]["battle_zone"])
            self.players[opponent]["battle_zone"] = []
            self.log.append(f"全体破壊！{destroyed_count}体破壊した")
        elif "相手のクリーチャーを1体破壊する" in ability:
            if len(self.players[opponent]["battle_zone"]) > 0:
                destroyed = self.players[opponent]["battle_zone"].pop(0)
                self.players[opponent]["graveyard"].append(destroyed)
                self.log.append(f"{destroyed['name']}を破壊した")
        
        # タップ効果
        if "相手のクリーチャーを全てタップする" in ability:
            for c in self.players[opponent]["battle_zone"]:
                c["tapped"] = True
            self.log.append("相手のクリーチャーを全てタップした")
        elif "相手のクリーチャーを1体タップする" in ability:
            if len(self.players[opponent]["battle_zone"]) > 0:
                self.players[opponent]["battle_zone"][0]["tapped"] = True
        
        # ハンデス
        if "相手の手札を見て1枚選び、捨てさせる" in ability:
            if len(self.players[opponent]["hand"]) > 0:
                discarded = self.players[opponent]["hand"].pop(0)
                self.players[opponent]["graveyard"].append(discarded)
                self.log.append(f"相手の手札から1枚捨てさせた")
    
    def process_spell_effect(self, player, spell):
        """呪文効果処理"""
        ability = spell.get("ability", "")
        opponent = "p2" if player == "p1" else "p1"
        
        # ドロー効果
        if "カードを3枚引く" in ability:
            self.draw_card(player, 3)
        elif "カードを2枚引く" in ability:
            self.draw_card(player, 2)
        elif "カードを1枚引く" in ability:
            self.draw_card(player, 1)
        
        # マナブースト
        if "自分の山札の上から5枚をマナゾーンに置く" in ability:
            for _ in range(5):
                if len(self.players[player]["deck"]) > 0:
                    mana_card = self.players[player]["deck"].pop(0)
                    mana_card["tapped"] = False
                    self.players[player]["mana"].append(mana_card)
        elif "自分の山札の上から2枚をマナゾーンに置く" in ability:
            for _ in range(2):
                if len(self.players[player]["deck"]) > 0:
                    mana_card = self.players[player]["deck"].pop(0)
                    mana_card["tapped"] = False
                    self.players[player]["mana"].append(mana_card)
        elif "自分の山札の上から1枚をマナゾーンに置く" in ability or "自分の山札の上から1枚目をマナゾーンに置く" in ability:
            if len(self.players[player]["deck"]) > 0:
                mana_card = self.players[player]["deck"].pop(0)
                mana_card["tapped"] = False
                self.players[player]["mana"].append(mana_card)
        
        # 除去効果
        if "相手のパワー5000以下のクリーチャーを1体破壊する" in ability:
            for creature in self.players[opponent]["battle_zone"]:
                if creature["power"] <= 5000:
                    self.players[opponent]["battle_zone"].remove(creature)
                    self.players[opponent]["graveyard"].append(creature)
                    self.log.append(f"{creature['name']}が破壊された")
                    break
        elif "相手のパワー4000以下のクリーチャーを1体破壊する" in ability:
            for creature in self.players[opponent]["battle_zone"]:
                if creature["power"] <= 4000:
                    self.players[opponent]["battle_zone"].remove(creature)
                    self.players[opponent]["graveyard"].append(creature)
                    self.log.append(f"{creature['name']}が破壊された")
                    break
        elif "相手のクリーチャーを1体破壊する" in ability:
            if len(self.players[opponent]["battle_zone"]) > 0:
                destroyed = self.players[opponent]["battle_zone"].pop(0)
                self.players[opponent]["graveyard"].append(destroyed)
                self.log.append(f"{destroyed['name']}が破壊された")
        
        # タップ効果
        if "相手のクリーチャーを1体タップする" in ability:
            if len(self.players[opponent]["battle_zone"]) > 0:
                self.players[opponent]["battle_zone"][0]["tapped"] = True
                self.log.append(f"{self.players[opponent]['battle_zone'][0]['name']}がタップされた")
        
        # 墓地回収
        if "自分の墓地からクリーチャーを1体、手札に戻す" in ability:
            if len(self.players[player]["graveyard"]) > 0:
                returned = self.players[player]["graveyard"].pop()
                self.players[player]["hand"].append(returned)
                self.log.append(f"{returned['name']}を墓地から手札に戻した")
        elif "自分の墓地からクリーチャーを1体、バトルゾーンに出す" in ability:
            if len(self.players[player]["graveyard"]) > 0:
                summoned = self.players[player]["graveyard"].pop()
                summoned["summoning_sick"] = False
                summoned["tapped"] = False
                self.players[player]["battle_zone"].append(summoned)
                self.log.append(f"{summoned['name']}を墓地からバトルゾーンに出した")
        
        # ハンデス
        if "相手の手札を見て1枚選び、捨てさせる" in ability:
            if len(self.players[opponent]["hand"]) > 0:
                discarded = self.players[opponent]["hand"].pop(0)
                self.players[opponent]["graveyard"].append(discarded)
                self.log.append(f"相手の{discarded['name']}を捨てさせた")
        
        # バフ効果
        if "そのクリーチャーは+3000され" in ability:
            if len(self.players[player]["battle_zone"]) > 0:
                self.players[player]["battle_zone"][0]["power"] += 3000
                self.players[player]["battle_zone"][0]["ability"] += ". スピードアタッカー"
    
    def attack(self, player, creature_id, target="player"):
        """攻撃"""
        opponent = "p2" if player == "p1" else "p1"
        
        for creature in self.players[player]["battle_zone"]:
            if creature["id"] == creature_id:
                if creature.get("summoning_sick", False) and "スピードアタッカー" not in creature.get("ability", "") and "このクリーチャーはバトルゾーンに出たターンも攻撃できる" not in creature.get("ability", ""):
                    return False, "召喚酔いで攻撃できません"
                if creature.get("tapped", False):
                    return False, "既にタップされています"
                
                creature["tapped"] = True
                
                if target == "player":
                    # ブレイカー数を取得
                    breaker_count = creature.get("breaker", 1)
                    shields_broken = 0
                    
                    for _ in range(breaker_count):
                        if self.players[opponent]["shields"] > 0:
                            self.players[opponent]["shields"] -= 1
                            shields_broken += 1
                            
                            # S・トリガー処理
                            if len(self.players[opponent].get("shield_cards", [])) > 0:
                                shield_card = self.players[opponent]["shield_cards"].pop(0)
                                self.players[opponent]["hand"].append(shield_card)
                                
                                if shield_card.get("shield_trigger", False):
                                    self.log.append(f"S・トリガー発動！{shield_card['name']}")
                                    self.trigger_shield_effect(opponent, shield_card)
                    
                    self.log.append(f"{creature['name']}が{shields_broken}枚シールドをブレイク！残り{self.players[opponent]['shields']}枚")
                    
                    if self.players[opponent]["shields"] == 0:
                        self.winner = player
                        self.log.append(f"{player}の勝利！")
                    return True, "攻撃成功"
                else:
                    # ブロッカーとバトル
                    for blocker in self.players[opponent]["battle_zone"]:
                        if blocker["id"] == target and "ブロッカー" in blocker.get("ability", ""):
                            # バトル処理
                            if creature["power"] >= blocker["power"]:
                                self.players[opponent]["battle_zone"].remove(blocker)
                                self.players[opponent]["graveyard"].append(blocker)
                                self.log.append(f"{blocker['name']}が破壊された")
                            if blocker["power"] >= creature["power"]:
                                self.players[player]["battle_zone"].remove(creature)
                                self.players[player]["graveyard"].append(creature)
                                self.log.append(f"{creature['name']}が破壊された")
                            return True, "バトル発生"
        return False, "攻撃失敗"
    
    def trigger_shield_effect(self, player, card):
        """S・トリガー効果処理（簡易版）"""
        ability = card.get("ability", "")
        opponent = "p2" if player == "p1" else "p1"
        
        if "カードを2枚引く" in ability:
            self.draw_card(player, 2)
        elif "カードを1枚引く" in ability:
            self.draw_card(player, 1)
        elif "相手のクリーチャーを1体タップする" in ability:
            if len(self.players[opponent]["battle_zone"]) > 0:
                self.players[opponent]["battle_zone"][0]["tapped"] = True
        elif "相手のクリーチャーを1体破壊する" in ability:
            if len(self.players[opponent]["battle_zone"]) > 0:
                destroyed = self.players[opponent]["battle_zone"].pop(0)
                self.players[opponent]["graveyard"].append(destroyed)
                self.log.append(f"S・トリガーで{destroyed['name']}が破壊された")
        elif "自分の山札の上から2枚をマナゾーンに置く" in ability:
            for _ in range(2):
                if len(self.players[player]["deck"]) > 0:
                    mana_card = self.players[player]["deck"].pop(0)
                    mana_card["tapped"] = False
                    self.players[player]["mana"].append(mana_card)
    
    def untap_all(self, player):
        """全てアンタップ"""
        for card in self.players[player]["mana"]:
            card["tapped"] = False
        for creature in self.players[player]["battle_zone"]:
            creature["tapped"] = False
            creature["summoning_sick"] = False
    
    def end_turn(self):
        """ターン終了"""
        self.turn = "p2" if self.turn == "p1" else "p1"
        self.turn_count += 1
        self.untap_all(self.turn)
        self.phase = "draw"
        self.draw_card(self.turn, 1)
        self.log.append(f"ターン{self.turn_count}: {self.turn}のターン")

# SocketIO イベント
@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('create_room')
def handle_create_room(data):
    room_id = data.get('room_id', 'room_' + str(random.randint(1000, 9999)))
    if room_id not in rooms:
        rooms[room_id] = DuelMastersGame()
        join_room(room_id)
        player_rooms[request.sid] = room_id
        emit('room_created', {'room_id': room_id, 'player': 'p1'})
    else:
        emit('error', {'msg': 'ルームが既に存在します'})

@socketio.on('join_room')
def handle_join_room(data):
    room_id = data['room_id']
    if room_id in rooms:
        join_room(room_id)
        player_rooms[request.sid] = room_id
        game = rooms[room_id]
        
        # プレイヤー番号を決定
        player_count = len([sid for sid, rid in player_rooms.items() if rid == room_id])
        player = 'p2' if player_count > 1 else 'p1'
        
        emit('room_joined', {'room_id': room_id, 'player': player})
        emit('player_joined', {'player': player}, room=room_id)
    else:
        emit('error', {'msg': 'ルームが見つかりません'})

@socketio.on('ready')
def handle_ready(data):
    room_id = player_rooms.get(request.sid)
    if room_id and room_id in rooms:
        game = rooms[room_id]
        player = data['player']
        game.players[player]['ready'] = True
        
        # デッキ構築
        game.build_deck(player)
        
        emit('player_ready', {'player': player}, room=room_id)
        
        # 両プレイヤーがreadyなら開始
        if game.players['p1']['ready'] and game.players['p2']['ready']:
            # シールド設置と初期ドロー
            game.setup_shields('p1')
            game.setup_shields('p2')
            game.draw_card('p1', 5)
            game.draw_card('p2', 5)
            game.log.append("ゲーム開始！")
            
            emit('game_start', get_game_state(game, 'p1'), room=room_id)

@socketio.on('charge_mana')
def handle_charge_mana(data):
    room_id = player_rooms.get(request.sid)
    if room_id and room_id in rooms:
        game = rooms[room_id]
        player = data['player']
        card_id = data['card_id']
        
        if game.turn == player:
            game.charge_mana(player, card_id)
            emit('game_update', get_game_state(game, 'p1'), room=room_id)

@socketio.on('summon_creature')
def handle_summon(data):
    room_id = player_rooms.get(request.sid)
    if room_id and room_id in rooms:
        game = rooms[room_id]
        player = data['player']
        card_id = data['card_id']
        
        if game.turn == player:
            success, msg = game.summon_creature(player, card_id)
            emit('game_update', get_game_state(game, 'p1'), room=room_id)

@socketio.on('cast_spell')
def handle_cast_spell(data):
    room_id = player_rooms.get(request.sid)
    if room_id and room_id in rooms:
        game = rooms[room_id]
        player = data['player']
        card_id = data['card_id']
        
        if game.turn == player:
            success, msg = game.cast_spell(player, card_id)
            emit('game_update', get_game_state(game, 'p1'), room=room_id)

@socketio.on('attack')
def handle_attack(data):
    room_id = player_rooms.get(request.sid)
    if room_id and room_id in rooms:
        game = rooms[room_id]
        player = data['player']
        creature_id = data['creature_id']
        target = data.get('target', 'player')
        
        if game.turn == player:
            success, msg = game.attack(player, creature_id, target)
            emit('game_update', get_game_state(game, 'p1'), room=room_id)

@socketio.on('end_turn')
def handle_end_turn(data):
    room_id = player_rooms.get(request.sid)
    if room_id and room_id in rooms:
        game = rooms[room_id]
        player = data['player']
        
        if game.turn == player:
            game.end_turn()
            emit('game_update', get_game_state(game, 'p1'), room=room_id)

def get_game_state(game, perspective):
    """ゲーム状態を取得"""
    return {
        'players': {
            'p1': {
                'hand_count': len(game.players['p1']['hand']),
                'hand': game.players['p1']['hand'] if perspective == 'p1' else [],
                'mana': game.players['p1']['mana'],
                'battle_zone': game.players['p1']['battle_zone'],
                'shields': game.players['p1']['shields'],
                'deck_count': len(game.players['p1']['deck']),
                'graveyard_count': len(game.players['p1']['graveyard'])
            },
            'p2': {
                'hand_count': len(game.players['p2']['hand']),
                'hand': game.players['p2']['hand'] if perspective == 'p2' else [],
                'mana': game.players['p2']['mana'],
                'battle_zone': game.players['p2']['battle_zone'],
                'shields': game.players['p2']['shields'],
                'deck_count': len(game.players['p2']['deck']),
                'graveyard_count': len(game.players['p2']['graveyard'])
            }
        },
        'turn': game.turn,
        'turn_count': game.turn_count,
        'phase': game.phase,
        'winner': game.winner,
        'log': game.log[-10:]  # 最新10件
    }

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
