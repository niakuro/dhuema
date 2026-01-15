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

# ===== 属性（文明）システム =====
# 5つの属性（文明）：
# - fire (火): 攻撃的、除去、速攻
# - water (水): ドロー、バウンス、コントロール
# - nature (自然): マナ加速、大型クリーチャー
# - light (光): 除去、タップ、ブロッカー
# - darkness (闇): 破壊、ハンデス、墓地利用
#
# 多色カード：複数の属性を持つ（例: ["fire", "darkness"]）
# 文明を対象とした効果：特定の属性のカードに影響を与える効果

# カードデータベース（システム対応済み・カードは空）
# 実装可能なシステム：
# 
# 【基本情報】
# - id: カードの一意なID（文字列）
# - name: カード名（文字列）
# - cost: コスト（数値）
# - civ: 属性（配列） 例: ["fire"] または ["fire", "darkness"]
#   * 単色: ["fire"], ["water"], ["nature"], ["light"], ["darkness"]
#   * 多色: ["fire", "darkness"], ["light", "water"] など
#   * 多色カードは含まれる全ての属性を持つ
# - type: "creature" または "spell"
# - race: 種族（文字列、クリーチャーのみ）
# - power: パワー（数値、クリーチャーのみ）
# - ability: 効果テキスト（文字列）
#
# 【特殊能力】
# - shield_trigger: True （S・トリガー）
# - breaker: 2 or 3 （W・ブレイカー、T・ブレイカー、デフォルトは1）
#
# 【ability に含めるキーワードによる自動処理】
# - "スピードアタッカー" → 召喚酔いなし
# - "ブロッカー" → 攻撃をブロック可能
# - "このクリーチャーがバトルゾーンに出た時" → 召喚時効果
# - "カードを○枚引く" → ドロー効果
# - "山札の上から○枚をマナゾーンに置く" → マナブースト
# - "クリーチャーを○体破壊する" → 除去効果
# - "クリーチャーを○体タップする" → タップ効果
# - "墓地から" → 墓地利用効果
# - "手札を見て" → ハンデス効果
#
# 【文明を対象とした効果の実装例】
# - "火のクリーチャーのパワー+1000" → 火属性を持つクリーチャー強化
# - "水の呪文のコスト-1" → 水属性を持つ呪文のコスト軽減
# - "自然のクリーチャーを破壊できない" → 自然属性への耐性
# ※ ability に文明名（"火"/"水"/"自然"/"光"/"闇"）を含めることで判定

CARD_DB = [
    # === 火文明テストカード ===
    {"id": "fire_test_1", "name": "火テスト1", "cost": 2, "power": 2000, "civ": ["fire"], "type": "creature", "race": "ドラゴン", "ability": "通常クリーチャー", "breaker": 1},
    {"id": "fire_test_2", "name": "火テスト2", "cost": 3, "power": 3000, "civ": ["fire"], "type": "creature", "race": "アーマロイド", "ability": "スピードアタッカー", "breaker": 1},
    {"id": "fire_test_3", "name": "火テスト3", "cost": 4, "power": 4000, "civ": ["fire"], "type": "creature", "race": "ドラゴン", "ability": "W・ブレイカー", "breaker": 2},
    {"id": "fire_test_4", "name": "火テスト4", "cost": 6, "power": 6000, "civ": ["fire"], "type": "creature", "race": "ドラゴン", "ability": "T・ブレイカー", "breaker": 3},
    {"id": "fire_test_5", "name": "火テスト5", "cost": 3, "civ": ["fire"], "type": "spell", "ability": "S・トリガー クリーチャーを1体破壊する", "shield_trigger": True},
    {"id": "fire_test_6", "name": "火テスト6", "cost": 5, "power": 5000, "civ": ["fire"], "type": "creature", "race": "ドラゴン", "ability": "このクリーチャーがバトルゾーンに出た時、カードを2枚引く", "breaker": 1},
    {"id": "fire_test_7", "name": "火テスト7", "cost": 4, "civ": ["fire"], "type": "spell", "ability": "クリーチャーを2体破壊する"},
    {"id": "fire_test_8", "name": "火テスト8", "cost": 3, "power": 3000, "civ": ["fire"], "type": "creature", "race": "アーマロイド", "ability": "スピードアタッカー W・ブレイカー", "breaker": 2},
    {"id": "fire_test_9", "name": "火テスト9", "cost": 4, "power": 4000, "civ": ["fire"], "type": "creature", "race": "ドラゴン", "ability": "ブロッカー", "breaker": 1},
    {"id": "fire_test_10", "name": "火テスト10", "cost": 2, "civ": ["fire"], "type": "spell", "ability": "山札の上から2枚をマナゾーンに置く"},
    
    # === 水文明テストカード ===
    {"id": "water_test_1", "name": "水テスト1", "cost": 2, "power": 1000, "civ": ["water"], "type": "creature", "race": "サイバーロード", "ability": "通常クリーチャー", "breaker": 1},
    {"id": "water_test_2", "name": "水テスト2", "cost": 3, "power": 2000, "civ": ["water"], "type": "creature", "race": "サイバーロード", "ability": "ブロッカー", "breaker": 1},
    {"id": "water_test_3", "name": "水テスト3", "cost": 4, "power": 3000, "civ": ["water"], "type": "creature", "race": "リキッド・ピープル", "ability": "W・ブレイカー", "breaker": 2},
    {"id": "water_test_4", "name": "水テスト4", "cost": 3, "civ": ["water"], "type": "spell", "ability": "カードを3枚引く"},
    {"id": "water_test_5", "name": "水テスト5", "cost": 2, "civ": ["water"], "type": "spell", "ability": "S・トリガー カードを2枚引く", "shield_trigger": True},
    {"id": "water_test_6", "name": "水テスト6", "cost": 5, "power": 4000, "civ": ["water"], "type": "creature", "race": "サイバーロード", "ability": "このクリーチャーがバトルゾーンに出た時、カードを2枚引く", "breaker": 1},
    {"id": "water_test_7", "name": "水テスト7", "cost": 6, "power": 5000, "civ": ["water"], "type": "creature", "race": "リキッド・ピープル", "ability": "T・ブレイカー", "breaker": 3},
    {"id": "water_test_8", "name": "水テスト8", "cost": 4, "power": 3000, "civ": ["water"], "type": "creature", "race": "サイバーロード", "ability": "スピードアタッカー ブロッカー", "breaker": 1},
    {"id": "water_test_9", "name": "水テスト9", "cost": 3, "civ": ["water"], "type": "spell", "ability": "クリーチャーを1体タップする"},
    {"id": "water_test_10", "name": "水テスト10", "cost": 5, "civ": ["water"], "type": "spell", "ability": "S・トリガー カードを3枚引く", "shield_trigger": True},
    
    # === 自然文明テストカード ===
    {"id": "nature_test_1", "name": "自然テスト1", "cost": 2, "power": 3000, "civ": ["nature"], "type": "creature", "race": "ビーストフォーク", "ability": "通常クリーチャー", "breaker": 1},
    {"id": "nature_test_2", "name": "自然テスト2", "cost": 3, "civ": ["nature"], "type": "spell", "ability": "山札の上から3枚をマナゾーンに置く"},
    {"id": "nature_test_3", "name": "自然テスト3", "cost": 4, "power": 5000, "civ": ["nature"], "type": "creature", "race": "ビーストフォーク", "ability": "W・ブレイカー", "breaker": 2},
    {"id": "nature_test_4", "name": "自然テスト4", "cost": 5, "power": 6000, "civ": ["nature"], "type": "creature", "race": "ジャイアント", "ability": "通常クリーチャー", "breaker": 1},
    {"id": "nature_test_5", "name": "自然テスト5", "cost": 2, "civ": ["nature"], "type": "spell", "ability": "S・トリガー 山札の上から2枚をマナゾーンに置く", "shield_trigger": True},
    {"id": "nature_test_6", "name": "自然テスト6", "cost": 6, "power": 7000, "civ": ["nature"], "type": "creature", "race": "ジャイアント", "ability": "T・ブレイカー", "breaker": 3},
    {"id": "nature_test_7", "name": "自然テスト7", "cost": 4, "power": 4000, "civ": ["nature"], "type": "creature", "race": "ビーストフォーク", "ability": "このクリーチャーがバトルゾーンに出た時、山札の上から2枚をマナゾーンに置く", "breaker": 1},
    {"id": "nature_test_8", "name": "自然テスト8", "cost": 5, "power": 5000, "civ": ["nature"], "type": "creature", "race": "ジャイアント", "ability": "ブロッカー", "breaker": 1},
    {"id": "nature_test_9", "name": "自然テスト9", "cost": 7, "power": 8000, "civ": ["nature"], "type": "creature", "race": "ジャイアント", "ability": "W・ブレイカー", "breaker": 2},
    {"id": "nature_test_10", "name": "自然テスト10", "cost": 3, "power": 4000, "civ": ["nature"], "type": "creature", "race": "ビーストフォーク", "ability": "スピードアタッカー", "breaker": 1},
    
    # === 光文明テストカード ===
    {"id": "light_test_1", "name": "光テスト1", "cost": 2, "power": 2000, "civ": ["light"], "type": "creature", "race": "イニシエート", "ability": "通常クリーチャー", "breaker": 1},
    {"id": "light_test_2", "name": "光テスト2", "cost": 3, "power": 2000, "civ": ["light"], "type": "creature", "race": "ベリー・レン", "ability": "ブロッカー", "breaker": 1},
    {"id": "light_test_3", "name": "光テスト3", "cost": 4, "power": 3000, "civ": ["light"], "type": "creature", "race": "イニシエート", "ability": "W・ブレイカー", "breaker": 2},
    {"id": "light_test_4", "name": "光テスト4", "cost": 3, "civ": ["light"], "type": "spell", "ability": "クリーチャーを2体タップする"},
    {"id": "light_test_5", "name": "光テスト5", "cost": 2, "civ": ["light"], "type": "spell", "ability": "S・トリガー クリーチャーを1体タップする", "shield_trigger": True},
    {"id": "light_test_6", "name": "光テスト6", "cost": 5, "power": 4000, "civ": ["light"], "type": "creature", "race": "ベリー・レン", "ability": "ブロッカー W・ブレイカー", "breaker": 2},
    {"id": "light_test_7", "name": "光テスト7", "cost": 6, "power": 5000, "civ": ["light"], "type": "creature", "race": "イニシエート", "ability": "T・ブレイカー", "breaker": 3},
    {"id": "light_test_8", "name": "光テスト8", "cost": 4, "power": 3000, "civ": ["light"], "type": "creature", "race": "イニシエート", "ability": "このクリーチャーがバトルゾーンに出た時、カードを2枚引く", "breaker": 1},
    {"id": "light_test_9", "name": "光テスト9", "cost": 5, "civ": ["light"], "type": "spell", "ability": "クリーチャーを1体破壊する"},
    {"id": "light_test_10", "name": "光テスト10", "cost": 4, "power": 3000, "civ": ["light"], "type": "creature", "race": "ベリー・レン", "ability": "ブロッカー スピードアタッカー", "breaker": 1},
    
    # === 闇文明テストカード ===
    {"id": "darkness_test_1", "name": "闇テスト1", "cost": 2, "power": 2000, "civ": ["darkness"], "type": "creature", "race": "ゴースト", "ability": "通常クリーチャー", "breaker": 1},
    {"id": "darkness_test_2", "name": "闇テスト2", "cost": 3, "civ": ["darkness"], "type": "spell", "ability": "クリーチャーを1体破壊する"},
    {"id": "darkness_test_3", "name": "闇テスト3", "cost": 4, "power": 4000, "civ": ["darkness"], "type": "creature", "race": "デーモン・コマンド", "ability": "W・ブレイカー", "breaker": 2},
    {"id": "darkness_test_4", "name": "闇テスト4", "cost": 2, "civ": ["darkness"], "type": "spell", "ability": "S・トリガー クリーチャーを1体破壊する", "shield_trigger": True},
    {"id": "darkness_test_5", "name": "闇テスト5", "cost": 5, "power": 5000, "civ": ["darkness"], "type": "creature", "race": "デーモン・コマンド", "ability": "このクリーチャーがバトルゾーンに出た時、相手の手札を見て1枚選び、捨てさせる", "breaker": 1},
    {"id": "darkness_test_6", "name": "闇テスト6", "cost": 6, "power": 6000, "civ": ["darkness"], "type": "creature", "race": "デーモン・コマンド", "ability": "T・ブレイカー", "breaker": 3},
    {"id": "darkness_test_7", "name": "闇テスト7", "cost": 4, "civ": ["darkness"], "type": "spell", "ability": "クリーチャーを2体破壊する"},
    {"id": "darkness_test_8", "name": "闇テスト8", "cost": 3, "power": 3000, "civ": ["darkness"], "type": "creature", "race": "ゴースト", "ability": "スピードアタッカー", "breaker": 1},
    {"id": "darkness_test_9", "name": "闇テスト9", "cost": 4, "civ": ["darkness"], "type": "spell", "ability": "墓地からクリーチャーを1体選び、手札に戻す"},
    {"id": "darkness_test_10", "name": "闇テスト10", "cost": 5, "power": 4000, "civ": ["darkness"], "type": "creature", "race": "デーモン・コマンド", "ability": "ブロッカー", "breaker": 1},
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
        self.attac属性（文明）情報を保持
                # 多色カードは複数の属性を持つが、表示用に最初の属性を使用
                if isinstance(mana_card.get("civ"), list):
                    mana_card["civ_display"] = mana_card["civ"][0]
                    mana_card["civilizations"] = mana_card["civ"]  # 全属性を保持
                else:
                    mana_card["civ_display"] = mana_card.get("civ", ["fire"])[0]
                    mana_card["civilizations"] = mana_card.get("civ", ["fire"])
                self.players[player]["mana"].append(mana_card)
                self.log.append(f"{player}が{mana_card['name']}をマナゾーンに置いた")
                return True
        return False
    
    def has_civilization(self, card, civ_name):
        """カードが特定の属性（文明）を持つかチェック"""
        card_civs = card.get("civ", [])
        if isinstance(card_civs, list):
            return civ_name in card_civs
        return card_civs == civ_name
    
    def count_civilizations(self, player, civ_name):
        """特定の属性（文明）を持つカードの数をカウント"""
        count = 0
        # バトルゾーン
        for card in self.players[player]["battle_zone"]:
            if self.has_civilization(card, civ_name):
                count += 1
        # マナゾーン
        for card in self.players[player]["mana"]:
            if self.has_civilization(card, civ_name):
                count += 1
        return count"cost"] <= 4:  # コスト4以下は2枚
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
            if car文明を対象としたコスト軽減効果のチェック（将来の拡張用）
                actual_cost = card["cost"]
                # 例: "水の呪文のコスト-1" のような効果があればここで処理
                
                if len(available_mana) < actual_cost:
                    return False, "マナが足りません"
                
                # マナをタップ
                for j in range(actual_cost):
                    available_mana[j]["tapped"] = True
                
                # 召喚
                creature = hand.pop(i)
                creature["summoning_sick"] = True
                creature["tapped"] = False
                # 属性情報を保持
                if "civ" in creature and isinstance(creature["civ"], list):
                    creature["civilizations"] = creature["civ"]"] = mana_card.get("civ", "fire")
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

@app.route('/api/cards')
def get_cards():
    """カードデータベースを取得"""
    return {'cards': CARD_DB}

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
