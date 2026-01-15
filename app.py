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

# カードデータベース（5文明：火、水、自然、光、闇）
CARD_DB = [
    # 火文明（攻撃的なクリーチャー）
    {"id": "fire_soldier", "name": "ファイアソルジャー", "cost": 2, "power": 2000, "civ": "fire", "type": "creature", "race": "ヒューマノイド", "ability": ""},
    {"id": "fire_bird", "name": "フレイムバード", "cost": 3, "power": 3000, "civ": "fire", "type": "creature", "race": "フェニックス", "ability": "スピードアタッカー"},
    {"id": "volcano_dragon", "name": "ボルケーノドラゴン", "cost": 5, "power": 6000, "civ": "fire", "type": "creature", "race": "ドラゴン", "ability": "パワーアタッカー+2000"},
    {"id": "inferno_gate", "name": "インフェルノゲート", "cost": 6, "power": 7000, "civ": "fire", "type": "creature", "race": "ドラゴン", "ability": "このクリーチャーがバトルゾーンに出た時、相手のパワー3000以下のクリーチャーを1体破壊する"},
    {"id": "fire_blast", "name": "ファイアブラスト", "cost": 3, "power": 0, "civ": "fire", "type": "spell", "ability": "相手のパワー3000以下のクリーチャーを1体破壊する"},
    
    # 水文明（ドロー・バウンス）
    {"id": "aqua_knight", "name": "アクアナイト", "cost": 2, "power": 1000, "civ": "water", "type": "creature", "race": "リキッド・ピープル", "ability": "ブロッカー"},
    {"id": "crystal_lancer", "name": "クリスタルランサー", "cost": 3, "power": 2000, "civ": "water", "type": "creature", "race": "リキッド・ピープル", "ability": "このクリーチャーがバトルゾーンに出た時、カードを1枚引く"},
    {"id": "storm_crawler", "name": "ストームクローラー", "cost": 4, "power": 3000, "civ": "water", "type": "creature", "race": "サイバーロード", "ability": "このクリーチャーがバトルゾーンに出た時、カードを2枚引く"},
    {"id": "aqua_surfer", "name": "アクアサーファー", "cost": 5, "power": 3000, "civ": "water", "type": "creature", "race": "リキッド・ピープル", "ability": "ブロッカー。このクリーチャーがバトルゾーンに出た時、カードを2枚引く"},
    {"id": "aqua_bounce", "name": "アクアバウンス", "cost": 2, "power": 0, "civ": "water", "type": "spell", "ability": "クリーチャーを1体、持ち主の手札に戻す"},
    
    # 自然文明（マナブースト・大型）
    {"id": "bronze_arm", "name": "ブロンズアーム", "cost": 2, "power": 2000, "civ": "nature", "type": "creature", "race": "ツリーフォーク", "ability": "このクリーチャーがバトルゾーンに出た時、自分のマナゾーンからカードを1枚、手札に戻してもよい"},
    {"id": "emerald_grass", "name": "エメラルドグラス", "cost": 3, "power": 2000, "civ": "nature", "type": "creature", "race": "ツリーフォーク", "ability": ""},
    {"id": "gigant_mantis", "name": "ギガントマンティス", "cost": 5, "power": 5000, "civ": "nature", "type": "creature", "race": "ジャイアント・インセクト", "ability": ""},
    {"id": "storm_horn", "name": "ストームホーン", "cost": 7, "power": 9000, "civ": "nature", "type": "creature", "race": "ホーンドビースト", "ability": "このクリーチャーは、相手プレイヤーを攻撃できない"},
    {"id": "natural_snare", "name": "ナチュラルスネア", "cost": 2, "power": 0, "civ": "nature", "type": "spell", "ability": "自分の山札の上から1枚目をマナゾーンに置く"},
    
    # 光文明（タップ・小型効率）
    {"id": "la_byle", "name": "ラビール", "cost": 2, "power": 2000, "civ": "light", "type": "creature", "race": "イニシエート", "ability": "ブロッカー"},
    {"id": "holy_spark", "name": "ホーリースパーク", "cost": 3, "power": 2000, "civ": "light", "type": "creature", "race": "スターライト・ツリー", "ability": "このクリーチャーがバトルゾーンに出た時、相手のクリーチャーを1体タップする"},
    {"id": "gran_gure", "name": "グラングレ", "cost": 4, "power": 3000, "civ": "light", "type": "creature", "race": "ガーディアン", "ability": "ブロッカー"},
    {"id": "diamond_sword", "name": "ダイヤモンドソード", "cost": 6, "power": 6000, "civ": "light", "type": "creature", "race": "ガーディアン", "ability": "ブロッカー。このクリーチャーがバトルゾーンに出た時、相手のクリーチャーを全てタップする"},
    {"id": "holy_awe", "name": "ホーリーオー", "cost": 3, "power": 0, "civ": "light", "type": "spell", "ability": "相手のクリーチャーを1体タップする"},
    
    # 闇文明（破壊・ハンデス）
    {"id": "death_smoke", "name": "デススモーク", "cost": 2, "power": 1000, "civ": "darkness", "type": "creature", "race": "ブレインジャッカー", "ability": "このクリーチャーがバトルゾーンに出た時、相手の手札を見て、その中から1枚選び、捨てさせる"},
    {"id": "skeleton_vice", "name": "スケルトンバイス", "cost": 3, "power": 2000, "civ": "darkness", "type": "creature", "race": "スケルトン", "ability": "スレイヤー（このクリーチャーをブロックしたクリーチャーを破壊する）"},
    {"id": "ballom_master", "name": "バロムマスター", "cost": 5, "power": 5000, "civ": "darkness", "type": "creature", "race": "デーモン・コマンド", "ability": "このクリーチャーがバトルゾーンに出た時、相手のクリーチャーを1体破壊する"},
    {"id": "dark_emperor", "name": "ダークエンペラー", "cost": 7, "power": 9000, "civ": "darkness", "type": "creature", "race": "デーモン・コマンド", "ability": "このクリーチャーがバトルゾーンに出た時、相手のクリーチャーを全て破壊する"},
    {"id": "death_blast", "name": "デスブラスト", "cost": 4, "power": 0, "civ": "darkness", "type": "spell", "ability": "相手のクリーチャーを1体破壊する"},
    
    # 多色・汎用カード
    {"id": "bronze_charger", "name": "ブロンズチャージャー", "cost": 1, "power": 1000, "civ": "fire", "type": "creature", "race": "ヒューマノイド", "ability": ""},
    {"id": "aqua_hulcus", "name": "アクアハルカス", "cost": 1, "power": 1000, "civ": "water", "type": "creature", "race": "リキッド・ピープル", "ability": ""},
    {"id": "spiral_gate", "name": "スパイラルゲート", "cost": 1, "power": 1000, "civ": "nature", "type": "creature", "race": "ツリーフォーク", "ability": ""},
    {"id": "shining_ball", "name": "シャイニングボール", "cost": 1, "power": 1000, "civ": "light", "type": "creature", "race": "イニシエート", "ability": ""},
    {"id": "poison_worm", "name": "ポイズンワーム", "cost": 1, "power": 1000, "civ": "darkness", "type": "creature", "race": "ワーム", "ability": ""},
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
                "graveyard": [],
                "ready": False
            },
            "p2": {
                "deck": [],
                "hand": [],
                "mana": [],
                "battle_zone": [],
                "shields": 5,
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
        """デッキを構築（各カード2枚ずつで40枚デッキ）"""
        deck = []
        for card in CARD_DB[:20]:  # 最初の20種類を使用
            deck.append(dict(card))
            deck.append(dict(card))
        random.shuffle(deck)
        self.players[player]["deck"] = deck
    
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
        for _ in range(5):
            if len(self.players[player]["deck"]) > 0:
                self.players[player]["deck"].pop(0)
    
    def charge_mana(self, player, card_id):
        """手札からマナゾーンにカードをチャージ"""
        hand = self.players[player]["hand"]
        for i, card in enumerate(hand):
            if card["id"] == card_id:
                mana_card = hand.pop(i)
                mana_card["tapped"] = False
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
        if "カードを1枚引く" in ability:
            self.draw_card(player, 1)
        elif "カードを2枚引く" in ability:
            self.draw_card(player, 2)
    
    def process_spell_effect(self, player, spell):
        """呪文効果処理（簡易版）"""
        ability = spell.get("ability", "")
        opponent = "p2" if player == "p1" else "p1"
        
        if "パワー3000以下のクリーチャーを1体破壊" in ability:
            # 実際はプレイヤーが選択するが、ここでは自動
            for creature in self.players[opponent]["battle_zone"]:
                if creature["power"] <= 3000:
                    self.players[opponent]["battle_zone"].remove(creature)
                    self.players[opponent]["graveyard"].append(creature)
                    self.log.append(f"{creature['name']}が破壊された")
                    break
    
    def attack(self, player, creature_id, target="player"):
        """攻撃"""
        opponent = "p2" if player == "p1" else "p1"
        
        for creature in self.players[player]["battle_zone"]:
            if creature["id"] == creature_id:
                if creature.get("summoning_sick", False) and "スピードアタッカー" not in creature.get("ability", ""):
                    return False, "召喚酔いで攻撃できません"
                if creature.get("tapped", False):
                    return False, "既にタップされています"
                
                creature["tapped"] = True
                
                if target == "player":
                    # シールドブレイク
                    if self.players[opponent]["shields"] > 0:
                        self.players[opponent]["shields"] -= 1
                        self.log.append(f"{creature['name']}がシールドをブレイク！残り{self.players[opponent]['shields']}枚")
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
