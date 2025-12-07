import cv2
import pygame
import os
import sys
import random
import time
import math
import numpy as np
from datetime import datetime
import pyttsx3
import threading
import qrcode
import getpass
import sounddevice as sd

# --- SESLİ ASİSTAN SINIFI (Threadli - Oyun Donmasın Diye) ---
class VoiceAssistant:
    def __init__(self):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 160)   # Konuşma hızı (Robotik)
            self.engine.setProperty('volume', 1.0) # Ses seviyesi
            
            # Varsa kadın/robot sesi seçmeye çalışalım
            voices = self.engine.getProperty('voices')
            for v in voices:
                if "Zira" in v.name or "David" in v.name: # Yaygın İngilizce sesler
                    self.engine.setProperty('voice', v.id)
                    break
        except:
            print("Ses motoru başlatılamadı.")
            self.engine = None

    def speak(self, text):
        if not self.engine: return
        # Konuşmayı ayrı bir işlemde (thread) yap ki oyun donmasın
        def _run():
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except: pass
        threading.Thread(target=_run, daemon=True).start()

# ==============================================================================
# 1. KONFİGÜRASYON (SYSTEM CONFIG)
# ==============================================================================
class Config:
    WIDTH = 900
    HEIGHT = 700
    FPS = 60
    TITLE = "AVATAR RUNNER: SİBER SAVAŞÇI"
    
    FILE_AVATAR = "avatar.jpg"
    FILE_SCORES = "scores.txt"
    
    # Renk Paleti (Neon Cyberpunk)
    C_BG = (5, 5, 10)              
    C_CYAN = (0, 255, 240)        
    C_MAGENTA = (255, 0, 80)      
    C_ORANGE = (255, 100, 0)      
    C_GOLD = (255, 215, 0)        
    C_LIME = (50, 255, 50)        
    C_WHITE = (240, 240, 255)     
    C_DARK_UI = (20, 30, 40)      
    C_RED = (255, 0, 0)           
    C_TERM_GREEN = (0, 255, 100)
    C_HOVER = (0, 40, 50)

# ==============================================================================
# 2. ASSET MANAGER
# ==============================================================================
class AssetCache:
    _circle_cache = {}
    
    @staticmethod
    def get_circle_surf(radius, color, alpha=255):
        key = (radius, color, alpha)
        if key not in AssetCache._circle_cache:
            s = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*color, alpha), (radius, radius), radius)
            AssetCache._circle_cache[key] = s.convert_alpha()
        return AssetCache._circle_cache[key]

# ==============================================================================
# 3. SOUND SYSTEM
# ==============================================================================
class SoundSystem:
    def __init__(self):
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
        except:
            print("Ses sürücüsü hatası. Sessiz mod.")
            self.disabled = True
            return
            
        self.disabled = False
        self.sounds = {}
        self.current_music = None
        
        self.assets = {
            "laser": "laser.wav",
            "explosion": "explosion.wav",
            "hit": "hit.wav",            
            "alert": "alert.wav",        
            "powerup": "powerup.wav",
            "ui": "ui.wav",              
            "music_bg": "music_bg.mp3",
            "music_boss": "music_boss.mp3"
        }
        
        for name, filename in self.assets.items():
            if filename.endswith(".wav") and os.path.exists(filename):
                try:
                    s = pygame.mixer.Sound(filename)
                    if name == "laser": s.set_volume(0.25)       
                    elif name == "explosion": s.set_volume(0.55)
                    elif name == "alert": s.set_volume(1.0)      
                    elif name == "ui": s.set_volume(0.4)
                    elif name == "hit": s.set_volume(0.7)
                    elif name == "powerup": s.set_volume(0.6)
                    self.sounds[name] = s
                except: pass

    def play_sfx(self, name):
        if self.disabled or name not in self.sounds: return
        self.sounds[name].play()

    def play_music(self, name):
        if self.disabled: return
        filename = self.assets.get(name)
        if self.current_music == name: return
        
        if filename and os.path.exists(filename):
            try:
                pygame.mixer.music.load(filename)
                pygame.mixer.music.set_volume(0.5)
                pygame.mixer.music.play(-1)
                self.current_music = name
            except: pass

    def stop_music(self):
        try: pygame.mixer.music.stop()
        except: pass

# ==============================================================================
# 4. GÖRSEL EFEKTLER (VFX & CRT)
# ==============================================================================
class CRTRenderer:
    def __init__(self, width, height):
        self.w, self.h = width, height
        scanlines = self.create_scanlines()
        vignette = self.create_vignette()
        self.static_overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        self.static_overlay.blit(scanlines, (0, 0))
        self.static_overlay.blit(vignette, (0, 0))
        self.crt_tint = pygame.Surface((width, height), pygame.SRCALPHA)
        self.crt_tint.fill((0, 10, 5, 5))
        self.static_overlay = self.static_overlay.convert_alpha()
        self.crt_tint = self.crt_tint.convert_alpha()

    def create_scanlines(self):
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for y in range(0, self.h, 4): 
            pygame.draw.line(s, (0, 0, 0, 25), (0, y), (self.w, y), 1)
            pygame.draw.line(s, (0, 0, 0, 10), (0, y+1), (self.w, y+1), 1)
        return s

    def create_vignette(self):
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        center = (self.w//2, self.h//2)
        for i in range(40):
            r = int(self.h * 0.75) + i * 10
            alpha = min(255, int(i * 3))
            pygame.draw.circle(s, (0,0,0,alpha), center, r, 15)
        return s

    def render(self, display_surf, trauma):
        if trauma > 0.6:
            offset = int(trauma * 4) 
            if offset > 0:
                rgb_split = display_surf.copy()
                display_surf.blit(rgb_split, (offset, 0), special_flags=pygame.BLEND_RGBA_ADD)
                display_surf.blit(rgb_split, (-offset, 0), special_flags=pygame.BLEND_RGBA_SUB)
        display_surf.blit(self.static_overlay, (0, 0))
        display_surf.blit(self.crt_tint, (0, 0), special_flags=pygame.BLEND_ADD)

class Particle:
    def __init__(self, x, y, vx, vy, color, size, decay, type="circle"):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.color = color
        self.size = size
        self.decay = decay
        self.life = 255.0
        self.type = type
        # Rastgele rotasyon (Kare parçalar için)
        self.angle = random.randint(0, 360) 
        self.rot_speed = random.uniform(-5, 5)

    def update(self):
        # Hareket
        self.x += self.vx
        self.y += self.vy
        self.angle += self.rot_speed

        # TİPE ÖZEL FİZİK KURALLARI
        if self.type == "spark":
            # Sürtünme: Hızla patlar, sonra yavaşlar (Hava direnci)
            self.vx *= 0.85
            self.vy *= 0.85
            self.size *= 0.9  # Kıvılcımlar küçülerek söner
        
        elif self.type == "smoke":
            # Duman yavaşlar ama yukarı süzülür
            self.vx *= 0.95
            self.vy = (self.vy * 0.95) - 0.05 # Hafif yukarı süzülme
            self.size += 0.3  # Duman genişler
            
        elif self.type == "debris":
            # Parçalar yerçekiminden etkilenir
            self.vy += 0.2 
            self.size *= 0.98

        elif self.type == "shockwave":
            self.size += 5  # Şok dalgası hızla büyür
            self.life -= 15 # Hızla kaybolur

        elif self.type == "shard": # Kalkan kırığı
            self.vx *= 0.92
            self.vy *= 0.92
            self.size *= 0.94

        self.life -= self.decay

    def draw(self, surface, dx, dy):
        if self.life <= 0 or self.size < 0.5: return
        alpha = max(0, min(255, int(self.life)))
        draw_pos = (int(self.x + dx), int(self.y + dy))

        # IŞIMA EFEKTİ (ADDITIVE BLENDING)
        # Bu, renklerin üst üste binince parlamasını sağlar
        
        if self.type == "smoke":
            # Duman karanlık olur, parlama yapmaz
            s = AssetCache.get_circle_surf(int(self.size), self.color, int(alpha * 0.6))
            surface.blit(s, (draw_pos[0]-self.size, draw_pos[1]-self.size))
            
        elif self.type == "shockwave":
             pygame.draw.circle(surface, (*self.color, alpha), draw_pos, int(self.size), 4)

        elif self.type == "shard":
            # Kalkan parçaları (Dönen kareler)
            s = pygame.Surface((int(self.size), int(self.size)), pygame.SRCALPHA)
            pygame.draw.rect(s, (*self.color, alpha), (0,0,int(self.size),int(self.size)))
            rot_s = pygame.transform.rotate(s, self.angle)
            surface.blit(rot_s, rot_s.get_rect(center=draw_pos), special_flags=pygame.BLEND_ADD)

        else: # Spark, Glow vb.
            # Parlayan çekirdek
            rad = int(self.size)
            if rad < 1: return
            
            # Glow efekti için Surface oluştur
            s = pygame.Surface((rad*4, rad*4), pygame.SRCALPHA)
            # Dış hale (soft)
            pygame.draw.circle(s, (*self.color, int(alpha*0.5)), (rad*2, rad*2), rad*2)
            # İç çekirdek (hard & bright)
            pygame.draw.circle(s, (255, 255, 255, alpha), (rad*2, rad*2), rad)
            
            surface.blit(s, (draw_pos[0]-rad*2, draw_pos[1]-rad*2), special_flags=pygame.BLEND_ADD)

class VFXSystem:
    def __init__(self):
        self.particles = []
        self.texts = []
        self.trauma = 0.0
        self.flash_alpha = 0
        self.font = pygame.font.SysFont("Impact", 36) 

    def add_trauma(self, amount): self.trauma = min(self.trauma + amount, 1.0)
    def trigger_flash(self, intensity=180): self.flash_alpha = intensity

    def get_shake(self):
        if self.trauma > 0:
            self.trauma = max(0, self.trauma - 0.02)
            shake = self.trauma ** 3 # Kübik sarsıntı (Daha sert vuruş hissi)
            return (random.uniform(-1, 1) * 40 * shake, random.uniform(-1, 1) * 40 * shake)
        return (0, 0)

    # GELİŞMİŞ PATLAMA
    def create_explosion(self, x, y, color, scale=1.0):
        # 1. Şok Dalgası (Hızlı)
        self.particles.append(Particle(x, y, 0, 0, color, 10*scale, 0, "shockwave"))
        
        # 2. Merkez Parlaması (Çok parlak beyaz)
        self.particles.append(Particle(x, y, 0, 0, (255,255,255), 30*scale, 20, "spark"))

        # 3. Kıvılcımlar (Hızlı patlar, çabuk söner)
        count = int(15 * scale)
        for _ in range(count):
            angle = random.uniform(0, 6.28)
            speed = random.uniform(5, 15) * scale
            self.particles.append(Particle(x, y, math.cos(angle)*speed, math.sin(angle)*speed, color, 4*scale, 8, "spark"))

        # 4. Duman (Yavaş genişler, koyu renk)
        smoke_col = (50, 50, 60)
        for _ in range(int(5 * scale)):
            angle = random.uniform(0, 6.28)
            speed = random.uniform(1, 4) * scale
            self.particles.append(Particle(x, y, math.cos(angle)*speed, math.sin(angle)*speed, smoke_col, 8*scale, 3, "smoke"))
            
    # VFXSystem sınıfının içine bu fonksiyonu ekle:
    def create_debris(self, rect, color):
        center_x, center_y = rect.centerx, rect.centery
        # Parçalanma efekti (Debris)
        for _ in range(10): 
            # Sağa sola rastgele fırlama ama hafif yukarı yönelim
            vx = random.uniform(-6, 6)
            vy = random.uniform(-8, 2)
            size = random.uniform(4, 9)
            # 'debris' tipi, yeni Particle sınıfında yerçekimi ile aşağı düşecek şekilde ayarlı
            self.particles.append(Particle(center_x, center_y, vx, vy, color, size, 3, "debris"))

    # YENİ: KALKAN KIRILMA EFEKTİ (Cam kırığı gibi)
    def create_shield_break(self, x, y):
        self.trigger_flash(100)
        self.add_trauma(0.6)
        
        # Mavi enerji halkası
        self.particles.append(Particle(x, y, 0, 0, (0, 255, 255), 50, 0, "shockwave"))
        
        # Cam kırıkları (Shards)
        for _ in range(20):
            angle = random.uniform(0, 6.28)
            speed = random.uniform(3, 10)
            p_col = (0, 255, 255) if random.random() > 0.5 else (200, 255, 255)
            self.particles.append(Particle(x, y, math.cos(angle)*speed, math.sin(angle)*speed, p_col, random.randint(5,10), 5, "shard"))

    # ... (emit_text ve update_draw kısımları aynı kalabilir, aynen kopyala) ...
    def emit_text(self, x, y, text, color):
        main_surf = self.font.render(text, True, color)
        outline_surf = self.font.render(text, True, (0, 0, 0))
        w, h = main_surf.get_width() + 4, main_surf.get_height() + 4
        final_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        final_surf.blit(outline_surf, (0, 2)); final_surf.blit(outline_surf, (4, 2))
        final_surf.blit(outline_surf, (2, 0)); final_surf.blit(outline_surf, (2, 4))
        final_surf.blit(main_surf, (2, 2))
        self.texts.append({"x": x - w//2, "y": y, "surf": final_surf, "life": 60, "vy": -3})

    def update_draw(self, screen, dx, dy):
        if len(self.particles) > 400: del self.particles[:50] # Limit arttırıldı
        for p in self.particles[:]:
            p.update()
            p.draw(screen, dx, dy)
            if p.life <= 0: self.particles.remove(p)
        for t in self.texts[:]:
            t["y"] += t["vy"]; t["vy"] *= 0.9; t["life"] -= 1.5
            if t["life"] <= 0: self.texts.remove(t); continue
            alpha = int((t["life"] / 60) * 255)
            if alpha < 0: alpha = 0
            t["surf"].set_alpha(alpha)
            screen.blit(t["surf"], (t["x"] + dx, t["y"] + dy))
        if self.flash_alpha > 0:
            flash_surf = pygame.Surface((Config.WIDTH, Config.HEIGHT))
            flash_surf.fill((255,255,255))
            flash_surf.set_alpha(self.flash_alpha)
            screen.blit(flash_surf, (0,0), special_flags=pygame.BLEND_ADD)
            self.flash_alpha -= 10

# ==============================================================================
# 5. YENİ NESİL ARAYÜZ MOTORU (ULTRA UI)
# ==============================================================================

class UIUtils:
    @staticmethod
    def draw_text_with_glow(surface, text, font, color, x, y, glow_color=(0, 255, 255), blur_radius=2):
        text_surf = font.render(text, True, color)
        rect = text_surf.get_rect(center=(x, y))
        glow_surf = font.render(text, True, glow_color)
        
        offsets = [(-2, -2), (2, 2), (-2, 2), (2, -2)]
        for off in offsets:
            surface.blit(glow_surf, (rect.x + off[0], rect.y + off[1]), special_flags=pygame.BLEND_ADD)
            
        surface.blit(text_surf, rect)
        return rect

    @staticmethod
    def draw_hex(surface, color, center, size, width=1):
        pts = []
        for i in range(6):
            angle_deg = 60 * i - 30
            angle_rad = math.radians(angle_deg)
            x = center[0] + size * math.cos(angle_rad)
            y = center[1] + size * math.sin(angle_rad)
            pts.append((x, y))
        pygame.draw.polygon(surface, color, pts, width)

class CinematicBoot:
    def __init__(self, screen, sound_sys): # <-- BURAYA sound_sys EKLENDİ
        self.screen = screen
        self.sound = sound_sys         # <-- SES SİSTEMİNİ KAYDETTİK
        self.w, self.h = Config.WIDTH, Config.HEIGHT
        self.font_term = pygame.font.SysFont("Consolas", 18)
        self.font_big = pygame.font.SysFont("Impact", 60)
        
        self.c_bg = (5, 10, 15)
        self.c_term = (0, 255, 120)
        self.c_dim = (0, 80, 40)
        self.c_highlight = (200, 255, 200)
        self.c_error = (255, 50, 50)

        # Boot Senaryosu
        self.sequence = [
            {"type": "wait", "duration": 60},
            {"type": "text", "msg": "BIOS DATE 12/01/2099 14:22:56 VER 9.04", "speed": 4},
            {"type": "text", "msg": "CHECKING POWER SILOS...", "speed": 3},
            {"type": "wait", "duration": 20},
            {"type": "text", "msg": "POWER LEVEL: %100 [OK]", "speed": 1, "color": self.c_highlight},
            {"type": "wait", "duration": 20},
            {"type": "text", "msg": "ESTABLISHING CPU CONNECTION...", "speed": 3},
            {"type": "wait", "duration": 20},
            {"type": "text", "msg": "CPU: QUANTUM CORE F86-PL @ 128.0 GHz", "speed": 2, "color": self.c_highlight},
            {"type": "wait", "duration": 20},
            {"type": "text", "msg": "CHECKING MEMORY BANKS...", "speed": 3},
            {"type": "wait", "duration": 20},
            {"type": "dump", "duration": 60},
            {"type": "text", "msg": "MEMORY INTEGRITY: %100 [OK]", "speed": 1, "color": self.c_highlight},
            {"type": "wait", "duration": 20},
            {"type": "text", "msg": "DETECTING NEURAL INTERFACE...", "speed": 2},
            {"type": "wait", "duration": 30},
            {"type": "glitch", "intensity": 10, "duration": 10},
            {"type": "text", "msg": ">> NEURAL LINK ESTABLISHED.", "speed": 0, "color": self.c_highlight},
            {"type": "text", "msg": "LOADING GRAPHICS DRIVER [INTERLOPER RXT]...", "speed": 1},
            {"type": "wait", "duration": 30},
            {"type": "decrypt", "msg": "SYSTEM SECURITY: UNLOCKED (!!!UNAUTHORIZED USER!!!)", "duration": 60},
            {"type": "wait", "duration": 30},
            {"type": "text", "msg": "UNAUTHORIZED ACCESS DETECTED... NOBODY IS SAFE.", "duration": 60, "speed": 4, "color": self.c_error},
            {"type": "wait", "duration": 30},
            {"type": "text", "msg": "PRESS ANY KEY TO CONTINUE...", "duration": 30}
            
        ]
        
        self.current_idx = 0
        self.timer = 0
        self.lines = []
        self.active_text = ""
        self.char_idx = 0
        self.hex_dump_lines = []
        self.decrypt_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#&@"

    def draw_grid(self):
        for i in range(0, self.w, 40):
            color = (0, 40, 20) if i % 120 == 0 else (0, 20, 10)
            pygame.draw.line(self.screen, color, (i, 0), (i, self.h), 1)
        for i in range(0, self.h, 40):
            color = (0, 40, 20) if i % 120 == 0 else (0, 20, 10)
            pygame.draw.line(self.screen, color, (0, i), (self.w, i), 1)

    def run(self):
        clock = pygame.time.Clock()
        active = True
        
        while active:
            self.screen.fill(self.c_bg)
            self.draw_grid()
            
            if self.current_idx < len(self.sequence):
                step = self.sequence[self.current_idx]
                
                if step["type"] == "text":
                    target_msg = step["msg"]
                    speed = step.get("speed", 1)
                    
                    if speed == 0:
                        self.active_text = target_msg
                        self.char_idx = len(target_msg)
                        self.sound.play_sfx("ui") # Tek seferlik ses
                    else:
                        if self.timer % speed == 0:
                            if self.char_idx < len(target_msg):
                                self.active_text += target_msg[self.char_idx]
                                self.char_idx += 1
                                # --- İŞTE BURADA SES ÇIKIYOR ---
                                # Her 2 harfte bir ses çıkar (çok gürültü olmasın diye)
                                if self.char_idx % 2 == 0:
                                    self.sound.play_sfx("ui") 
                    
                    if self.char_idx >= len(target_msg):
                        if self.timer > 10: 
                            col = step.get("color", self.c_term)
                            self.lines.append({"t": self.active_text, "c": col})
                            self.active_text = ""; self.char_idx = 0; self.current_idx += 1; self.timer = 0
                        else: self.timer += 1
                    else: self.timer += 1

                elif step["type"] == "wait":
                    self.timer += 1
                    if self.timer >= step["duration"]: self.current_idx += 1; self.timer = 0

                elif step["type"] == "dump":
                    self.timer += 1
                    
                    # --- EASTER EGG: HAYALET MESAJLAR ---
                    # %5 ihtimalle hex kodu yerine yardım çığlığı bas
                    if random.random() < 0.05:
                        ghost_msgs = ["   YARDIM ET    ", " BENI SILMEDILER", "  BURADAYIM...  ", "  GOLGE DUYUYOR ", " SISTEM YALAN "]
                        msg = random.choice(ghost_msgs)
                        # Mesajı kırmızımsı bir renkle ekle ki fark edilsin
                        self.lines.append({"t": msg.center(40), "c": (150, 0, 0)})
                        self.sound.play_sfx("ui") # Hafif bir 'bip' sesi
                    else:
                        # Normal Hex Akışı
                        hex_line = f"0x{random.randint(0,999999):06X}  " * 4
                        self.lines.append({"t": hex_line, "c": self.c_dim})
                    
                    if len(self.lines) > 18: self.lines.pop(0)
                    if self.timer % 4 == 0: self.sound.play_sfx("ui") 
                    if self.timer >= step["duration"]: self.current_idx += 1; self.timer = 0

                elif step["type"] == "glitch":
                    self.timer += 1
                    intensity = step["intensity"]
                    dx = random.randint(-intensity, intensity); dy = random.randint(-intensity, intensity)
                    temp = self.screen.copy()
                    self.screen.fill((random.randint(0,50), 0, 0))
                    self.screen.blit(temp, (dx, dy))
                    if self.timer % 5 == 0: self.sound.play_sfx("ui") # Hata sesi
                    if self.timer >= step["duration"]: self.current_idx += 1; self.timer = 0

                elif step["type"] == "decrypt":
                    self.timer += 1
                    target_msg = step["msg"]
                    percent = self.timer / step["duration"]
                    revealed = int(len(target_msg) * percent)
                    display_txt = target_msg[:revealed]
                    for _ in range(len(target_msg) - revealed): display_txt += random.choice(self.decrypt_chars)
                    self.active_text = display_txt
                    if self.timer % 3 == 0: self.sound.play_sfx("ui") # Şifre çözme sesi
                    if self.timer >= step["duration"]:
                        self.lines.append({"t": target_msg, "c": (0, 255, 255)})
                        self.active_text = ""; self.current_idx += 1; self.timer = 0
                    
                """
                elif step["type"] == "logo":
                    self.timer += 1
                    alpha = min(255, self.timer * 5)
                    title = self.font_big.render("AVATAR RUNNER", True, (255, 255, 255)); title.set_alpha(alpha)
                    rect = title.get_rect(center=(self.w//2, self.h//2))
                    glow = self.font_big.render("AVATAR RUNNER", True, (0, 255, 255)); glow.set_alpha(max(0, alpha - 50))
                    self.screen.blit(glow, (rect.x-2, rect.y-2)); self.screen.blit(title, rect)
                    if self.timer >= step["duration"]: active = False
                """

            y = 40
            for line in self.lines[-15:]:
                self.screen.blit(self.font_term.render(line["t"], True, line["c"]), (40, y)); y += 24
            if self.active_text:
                cur = "_" if (pygame.time.get_ticks() // 200) % 2 else ""
                self.screen.blit(self.font_term.render(self.active_text + cur, True, self.c_highlight), (40, y))

            for i in range(0, self.h, 2): pygame.draw.line(self.screen, (0, 0, 0), (0, i), (self.w, i), 1)
            pygame.draw.rect(self.screen, (0,0,0), (0,0,self.w,self.h), 20)
            pygame.display.flip(); clock.tick(60)
            for e in pygame.event.get():
                if e.type == pygame.QUIT: sys.exit()
                if e.type == pygame.KEYDOWN: active = False

class CyberButton:
    def __init__(self, x, y, w, h, text, cmd):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.cmd = cmd
        self.hover_anim = 0.0
        self.font = pygame.font.SysFont("Impact", 28)
        self.font_small = pygame.font.SysFont("Consolas", 10)
    
    def draw(self, screen, mx, my):
        hover = self.rect.collidepoint(mx, my)
        target = 1.0 if hover else 0.0
        self.hover_anim += (target - self.hover_anim) * 0.2
        
        base_col = (10, 20, 30, 200)
        border_col = (0, 255, 255)
        if hover: border_col = (255, 0, 80)
        
        expand = self.hover_anim * 10
        draw_rect = self.rect.inflate(expand, 0)
        s = pygame.Surface((draw_rect.w, draw_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(s, base_col, (0,0,draw_rect.w, draw_rect.h))
        
        corner_len = 15 + (self.hover_anim * 10)
        cols = (*border_col, int(150 + self.hover_anim*105))
        
        pygame.draw.line(s, cols, (0,0), (corner_len, 0), 2)
        pygame.draw.line(s, cols, (0,0), (0, corner_len), 2)
        pygame.draw.line(s, cols, (draw_rect.w, draw_rect.h), (draw_rect.w-corner_len, draw_rect.h), 2)
        pygame.draw.line(s, cols, (draw_rect.w, draw_rect.h), (draw_rect.w, draw_rect.h-corner_len), 2)
        
        screen.blit(s, draw_rect)
        
        txt_offset = 0
        if hover and random.random() > 0.9: txt_offset = random.randint(-2, 2)
        
        txt_col = (255, 255, 255) if hover else (0, 200, 200)
        txt_surf = self.font.render(self.text, True, txt_col)
        screen.blit(txt_surf, (draw_rect.centerx - txt_surf.get_width()//2 + txt_offset, draw_rect.centery - txt_surf.get_height()//2))
        
        if hover:
            dec = self.font_small.render(f"HEX:{random.randint(100,999)}", True, (100,100,100))
            screen.blit(dec, (draw_rect.x, draw_rect.y - 12))

        return hover

# ==============================================================================
# 6. AVATAR CAM (TÜRKÇE) - GÜÇLENDİRİLMİŞ YÜZ TANIMA MODÜLÜ
# ==============================================================================
# ==============================================================================
# 6. BİYOMETRİK TARAMA (AVATAR CAM - GECE GÖRÜŞ MODU)
# ==============================================================================
class AvatarCam:
    def __init__(self):
        self.w, self.h = Config.WIDTH, Config.HEIGHT
        self.font = pygame.font.SysFont("Consolas", 18)
        self.font_big = pygame.font.SysFont("Consolas", 30, bold=True)
        self.sound = SoundSystem() # Ses efekti için
        
        # OpenCV Başlatma
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened(): self.cap = cv2.VideoCapture(0)
        
        # Yüz Tanıma
        path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(path)
        
        self.scan_line_y = 0
        self.flash_timer = 0
        self.captured_frame = None

    def apply_night_vision(self, frame):
        """Görüntüyü yeşil tonlu gece görüşüne çevirir."""
        # 1. Griye çevir
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # 2. Gürültü ekle (Noise)
        noise = np.random.randint(0, 30, gray.shape, dtype='uint8')
        gray_noisy = cv2.add(gray, noise)
        # 3. Yeşile boya (BGR formatında Green kanalı)
        # B=0, G=gray, R=0
        zeros = np.zeros_like(gray)
        night_vision = cv2.merge([zeros, gray_noisy, zeros])
        return night_vision, gray

    def run(self):
        screen = pygame.display.get_surface()
        clock = pygame.time.Clock()
        crt = CRTRenderer(Config.WIDTH, Config.HEIGHT)
        
        running = True
        
        while running:
            # 1. Kameradan Görüntü Al
            ret, frame = self.cap.read()
            if not ret: 
                # Kamera yoksa siyah ekran ve hata mesajı
                screen.fill((0, 20, 0))
                txt = self.font.render("NO SIGNAL", True, (0, 255, 0))
                screen.blit(txt, (self.w//2 - 50, self.h//2))
                pygame.display.flip()
                continue

            frame = cv2.flip(frame, 1) # Aynalama
            
            # 2. Görüntü İşleme (Gece Görüşü)
            nv_frame, gray_frame = self.apply_night_vision(frame)
            
            # 3. Yüz Tanıma
            faces = self.face_cascade.detectMultiScale(gray_frame, 1.1, 4)
            face_detected = len(faces) > 0
            
            # Yüzleri kare içine al (OpenCV üzerinde çizim)
            for (x, y, w, h) in faces:
                # Köşeli parantez efekti
                c = (0, 255, 0)
                l = 20
                t = 2
                cv2.line(nv_frame, (x, y), (x+l, y), c, t); cv2.line(nv_frame, (x, y), (x, y+l), c, t)
                cv2.line(nv_frame, (x+w, y), (x+w-l, y), c, t); cv2.line(nv_frame, (x+w, y), (x+w, y+l), c, t)
                cv2.line(nv_frame, (x, y+h), (x+l, y+h), c, t); cv2.line(nv_frame, (x, y+h), (x, y+h-l), c, t)
                cv2.line(nv_frame, (x+w, y+h), (x+w-l, y+h), c, t); cv2.line(nv_frame, (x+w, y+h), (x+w, y+h-l), c, t)
                
                # Koordinat yazısı
                cv2.putText(nv_frame, f"TARGET_ID: {x+y}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1)

            # 4. Pygame Yüzeyine Çevir
            # OpenCV (BGR) -> Pygame (RGB)
            # Ama biz zaten yeşil yaptık (0, G, 0), BGR ve RGB aynı görünür yeşilde ama doğrusunu yapalım.
            rgb_frame = cv2.cvtColor(nv_frame, cv2.COLOR_BGR2RGB)
            
            # Görüntüyü ekrana sığacak şekilde ölçekle (Aspect Ratio koruyarak)
            h_cam, w_cam, _ = rgb_frame.shape
            scale = min(self.w / w_cam, self.h / h_cam)
            new_w, new_h = int(w_cam * scale), int(h_cam * scale)
            rgb_frame = cv2.resize(rgb_frame, (new_w, new_h))
            
            # Surface oluştur
            surf = pygame.image.frombuffer(rgb_frame.tobytes(), (new_w, new_h), "RGB")
            
            # Ekrana ortalayarak bas
            screen.fill((0, 0, 0))
            dx = (self.w - new_w) // 2
            dy = (self.h - new_h) // 2
            screen.blit(surf, (dx, dy))

            # 5. Arayüz (HUD) Çizimi (Pygame ile)
            
            # Tarama Çizgisi (Scanline)
            self.scan_line_y += 4
            if self.scan_line_y > self.h: self.scan_line_y = 0
            pygame.draw.line(screen, (0, 255, 0), (0, self.scan_line_y), (self.w, self.scan_line_y), 1)
            
            # Köşe Yazıları
            if int(time.time() * 2) % 2:
                screen.blit(self.font_big.render("● REC", True, (255, 0, 0)), (40, 40))
            
            screen.blit(self.font.render("BIOMETRIC SCAN: ACTIVE", True, (0, 255, 0)), (40, self.h - 60))
            
            if face_detected:
                status = self.font.render(f"SUBJECT DETECTED [{len(faces)}]", True, (0, 255, 0))
                # Hedef kilitlendiğinde etrafına büyük çerçeve
                pygame.draw.rect(screen, (0, 255, 0), (dx+20, dy+20, new_w-40, new_h-40), 2)
            else:
                status = self.font.render("SEARCHING SUBJECT...", True, (0, 100, 0))
            
            screen.blit(status, (self.w - status.get_width() - 40, 40))

            # --- EASTER EGG: SUBJECT LOST (GÖZ TEMASI) ---
            if not face_detected:
                # 1. Kırmızı Karıncalanma Efekti
                noise = pygame.Surface((self.w, self.h))
                noise.set_alpha(80) # Yarı saydam
                noise.fill((50, 0, 0)) # Koyu kırmızı filtre
                
                # Rastgele çizgiler (Static Noise)
                for _ in range(50):
                    nx = random.randint(0, self.w)
                    ny = random.randint(0, self.h)
                    pygame.draw.line(noise, (255, 0, 0), (nx, ny), (nx + random.randint(-50,50), ny), 2)
                
                screen.blit(noise, (0,0))
                
                # 2. Ürkütücü Yazı (Yanıp Sönen)
                if int(time.time() * 5) % 2 == 0:
                    warn_font = pygame.font.SysFont("Impact", 70)
                    warn_msg = warn_font.render("SUBJECT LOST // LOOK AT ME", True, (255, 0, 0))
                    # Yazıyı ekranın ortasına koy
                    screen.blit(warn_msg, (self.w//2 - warn_msg.get_width()//2, self.h//2))
            
            # Alt Bar Talimatları
            instr = "[SPACE] CAPTURE FRAME    [ESC] ABORT"
            if self.captured_frame is not None:
                instr = "[ENTER] SAVE & UPLOAD    [R] RETRY"
            
            instr_surf = self.font.render(instr, True, (200, 255, 200))
            pygame.draw.rect(screen, (0, 20, 0), (0, self.h-40, self.w, 40))
            screen.blit(instr_surf, (self.w//2 - instr_surf.get_width()//2, self.h - 30))

            # Flaş Efekti
            if self.flash_timer > 0:
                flash = pygame.Surface((self.w, self.h))
                flash.fill((255, 255, 255))
                flash.set_alpha(self.flash_timer)
                screen.blit(flash, (0,0))
                self.flash_timer -= 15

            # Fotoğraf Dondurma Modu
            if self.captured_frame is not None:
                screen.blit(self.captured_frame, (dx, dy))
                overlay = pygame.Surface((self.w, self.h))
                overlay.set_alpha(100)
                overlay.fill((0, 50, 0))
                screen.blit(overlay, (0,0))
                
                msg = self.font_big.render("IMAGE FROZEN", True, (255, 255, 255))
                screen.blit(msg, (self.w//2 - msg.get_width()//2, self.h//2))

            crt.render(screen, 0)
            pygame.display.flip()
            clock.tick(30) # Kamera 30 FPS yeterli

            # Eventler
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.cap.release()
                    return False
                    
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        self.cap.release()
                        return False
                        
                    if self.captured_frame is None:
                        # Fotoğraf Çek (Space)
                        if e.key == pygame.K_SPACE:
                            self.sound.play_sfx("ui")
                            self.flash_timer = 200
                            # Şu anki ekranı dondur (Pygame yüzeyi olarak sakla)
                            self.captured_frame = surf.copy()
                            # Diske kaydetmek için ham OpenCV karesini de saklayabiliriz ama 
                            # efektli halini kaydetmek daha havalı:
                            self.save_cache = nv_frame.copy() 
                    else:
                        # Kaydet (Enter)
                        if e.key == pygame.K_RETURN:
                            self.sound.play_sfx("powerup")
                            # Yüzü kırp (kabaca ortadan alalım veya tüm ekranı)
                            # Basit olsun, yakalanan efektli kareyi kaydedelim
                            cv2.imwrite(Config.FILE_AVATAR, self.save_cache)
                            self.cap.release()
                            return True
                        # Yeniden Dene (R)
                        elif e.key == pygame.K_r:
                            self.captured_frame = None

        self.cap.release()
        return False

# ==============================================================================
# 7. OYUN MOTORU (TÜRKÇE)
# ==============================================================================
class BossEnemy:
    def __init__(self, difficulty_mult):
        self.w, self.h = 160, 100
        self.x = Config.WIDTH // 2 - self.w // 2
        self.y = -150
        self.target_y = 50
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.max_hp = 500 * difficulty_mult
        self.hp = self.max_hp
        self.vx = 3
        self.phase = 1 
        self.bullets = []
        self.shoot_timer = 0
        self.entrance = True
        self.oscillation = 0

    def update(self, player_rect):
        if self.entrance:
            self.y += 2
            if self.y >= self.target_y:
                self.y = self.target_y; self.entrance = False
            self.rect.y = int(self.y)
            return
        if self.hp < self.max_hp * 0.5: self.phase = 2; speed_mult = 2.0
        else: speed_mult = 1.0
        self.x += self.vx * speed_mult
        if self.x <= 20 or self.x >= Config.WIDTH - self.w - 20: self.vx *= -1
        self.oscillation += 0.1
        self.rect.y = int(self.y + math.sin(self.oscillation) * 10)
        self.rect.x = int(self.x)

        shoot_cd = 40 if self.phase == 2 else 70
        self.shoot_timer += 1
        if self.shoot_timer >= shoot_cd:
            self.shoot_timer = 0
            center_x = self.rect.centerx; center_y = self.rect.bottom
            angle = math.atan2(player_rect.centery - center_y, player_rect.centerx - center_x)
            b_speed = 7 if self.phase == 1 else 12
            vx = math.cos(angle) * b_speed; vy = math.sin(angle) * b_speed
            self.bullets.append([center_x, center_y, vx, vy])
            if self.phase == 2:
                self.bullets.append([center_x, center_y, vx-2, vy])
                self.bullets.append([center_x, center_y, vx+2, vy])
        for b in self.bullets[:]:
            b[0] += b[2]; b[1] += b[3]
            if b[1] > Config.HEIGHT: self.bullets.remove(b)

    def draw(self, screen, dx, dy):
        base_color = Config.C_RED if (self.phase == 2 and int(time.time()*10)%2) else Config.C_MAGENTA
        draw_x, draw_y = self.rect.x + dx, self.rect.y + dy
        pygame.draw.rect(screen, (20, 20, 30), (draw_x, draw_y, self.w, self.h), border_radius=10)
        pygame.draw.rect(screen, base_color, (draw_x, draw_y, self.w, self.h), 3, border_radius=10)
        pygame.draw.line(screen, base_color, (draw_x, draw_y+20), (draw_x-30, draw_y+50), 4)
        pygame.draw.line(screen, base_color, (draw_x+self.w, draw_y+20), (draw_x+self.w+30, draw_y+50), 4)
        for b in self.bullets:
            pygame.draw.circle(screen, Config.C_RED, (int(b[0]+dx), int(b[1]+dy)), 8)
            pygame.draw.circle(screen, Config.C_WHITE, (int(b[0]+dx), int(b[1]+dy)), 3)
        bar_w = self.w; hp_pct = max(0, self.hp / self.max_hp)
        pygame.draw.rect(screen, (50,0,0), (draw_x, draw_y - 20, bar_w, 8))
        pygame.draw.rect(screen, Config.C_RED, (draw_x, draw_y - 20, bar_w * hp_pct, 8))

class LaserBeam:
    def __init__(self, start, end, color):
        self.start, self.end, self.color = start, end, color
        self.life = 5  
    def draw(self, surface, dx, dy):
        if self.life > 0:
            start_pos = (self.start[0] + dx, self.start[1] + dy)
            end_pos = (self.end[0] + dx, self.end[1] + dy)
            pygame.draw.line(surface, self.color, start_pos, end_pos, int(self.life))
            pygame.draw.line(surface, (255, 255, 255), start_pos, end_pos, 1)
            self.life -= 1

# ==============================================================================
# 7. OYUN MOTORU (DRONE OPERATOR - TACTICAL OVERHAUL)
# ==============================================================================
# ==============================================================================
# 7. OYUN MOTORU (ULTIMATE EDITION - 6DOF & OVERHEAT MECHANICS)
# ==============================================================================
# ==============================================================================
# 7. OYUN MOTORU (FINAL CUT - TACTICAL WARFARE)
# ==============================================================================
# ==============================================================================
# 7. OYUN MOTORU (THE VOICE UPDATE)
# ==============================================================================
class GameEngine:
    def __init__(self, screen, sound_sys):
        self.screen = screen
        self.sound = sound_sys 
        self.clock = pygame.time.Clock()
        self.vfx = VFXSystem()
        self.crt = CRTRenderer(Config.WIDTH, Config.HEIGHT)
        
        # --- YENİ: ROBOT SESİ ---
        self.voice = VoiceAssistant() # <-- SESLİ ASİSTAN BAŞLATILDI
        
        # --- HUD & UI ---
        self.font_hud = pygame.font.SysFont("Consolas", 12)
        self.font_alert = pygame.font.SysFont("Impact", 40)
        self.font_big = pygame.font.SysFont("Impact", 80)
        
        # Oyun Alanı
        self.play_rect = pygame.Rect(180, 0, Config.WIDTH - 360, Config.HEIGHT)
        self.logs = ["SYSTEM_INIT...", "DRONE_LINK_STABLE", "WEAPONS_FREE"]
        self.log_timer = 0
        
        # --- OYUNCU ---
        self.player_pos = pygame.Vector2(Config.WIDTH//2, Config.HEIGHT-150)
        self.velocity = pygame.Vector2(0, 0)
        self.heat = 0.0      
        self.overheat = False 
        self.adrenalin = 0.0 
        self.adrenalin_active = False

        # --- SKOR & KOMBO ---
        self.combo_count = 0
        self.combo_timer = 0
        self.combo_multiplier = 1
        
        # --- NESNELER ---
        self.lasers = []
        self.boss = None
        self.next_boss_score = 1000
        self.delayed_kills = []
        self.enemies = [] 
        self.pwrs = [] 
        self.grid_offset = 0

        # --- KIRIK EKRAN DEĞİŞKENLERİ ---
        self.cracks = [] # Çatlak koordinatlarını tutacak

        # --- EASTER EGG: BINARY FISILTILAR ---
        self.whisper_timer = 0
        self.whisper_text = ""
        self.whisper_pos = (0, 0)
        self.whisper_font = pygame.font.SysFont("Consolas", 12) # Çok küçük, terminal fontu
        # --- MORS ALFABESİ ---
        self.morse_buffer = [] # Basış sürelerini tutar
        self.last_ctrl_press = 0
        self.sos_cooldown = False
    # ... (draw_enemy_visuals, draw_powerup, draw_tactical_grid, draw_hud_panels, draw_target_box, draw_terminal_bg AYNI KALSIN) ...
    # KODUN BU KISMI ÇOK UZUN OLMASIN DİYE YUKARIDAKİ YARDIMCI METODLARI SİLMİYORUM. 
    # LÜTFEN ÖNCEKİ KODDAKİ ÇİZİM FONKSİYONLARINI (draw_*) BURADA KORU.
    # AŞAĞIDA SADECE DEĞİŞEN 'run' METODUNU VE EKLENEN SESLERİ GÖSTERİYORUM.
    
    # KOPYALA-YAPIŞTIR KOLAYLIĞI İÇİN YARDIMCI METODLARI TEKRAR VERİYORUM:
    def draw_enemy_visuals(self, enemy, dx, dy):
        x = enemy.rect.x + dx; y = enemy.rect.y + dy; cx, cy = x + enemy.rect.w // 2, y + enemy.rect.h // 2
        if enemy.type == "KAMIKAZE":
            pts = [(cx, y), (x + enemy.rect.w, y + enemy.rect.h), (x, y + enemy.rect.h)]
            pygame.draw.polygon(self.screen, (50, 50, 50), pts); pygame.draw.polygon(self.screen, (255, 100, 0), pts, 2)
            pygame.draw.circle(self.screen, (255, 200, 0), (cx, y + enemy.rect.h), 5)
        elif enemy.type == "DRONE":
            pygame.draw.rect(self.screen, (30, 40, 50), (x, y, 40, 40)); pygame.draw.rect(self.screen, (0, 200, 200), (x, y, 40, 40), 2)
            pygame.draw.circle(self.screen, (255, 0, 0), (cx, cy), 6 + int(time.time() * 5) % 3); pygame.draw.circle(self.screen, (255, 100, 100), (cx, cy), 2)

    def draw_powerup(self, pwr, dx, dy):
        x, y = pwr["r"].x + dx, pwr["r"].y + dy
        if pwr["t"] == "RPR": c = (0, 255, 0)    
        elif pwr["t"] == "SHD": c = (0, 255, 255)
        elif pwr["t"] == "CLN": c = (255, 255, 0)
        pygame.draw.rect(self.screen, (0, 50, 0), (x, y, 30, 30)); pygame.draw.rect(self.screen, c, (x, y, 30, 30), 2)
        txt = self.font_hud.render(pwr["t"], True, c); self.screen.blit(txt, (x + 4, y + 8))
        pygame.draw.line(self.screen, (c[0], c[1], c[2], 50), (x+15, y), (x+15, y-500), 1)

    def draw_tactical_grid(self, speed):
        base_col = (20, 0, 0) if self.adrenalin_active else (0, 15, 5); line_col = (100, 0, 0) if self.adrenalin_active else (0, 40, 20)
        pygame.draw.rect(self.screen, base_col, self.play_rect)
        for x in range(self.play_rect.left, self.play_rect.right, 60): pygame.draw.line(self.screen, line_col, (x, 0), (x, Config.HEIGHT), 1)
        self.grid_offset = (self.grid_offset + speed * 2) % 60
        for y in range(0, Config.HEIGHT, 60):
            draw_y = y + self.grid_offset
            if draw_y < Config.HEIGHT:
                alpha = int((draw_y / Config.HEIGHT) * 100)
                c_r = alpha if self.adrenalin_active else 0; c_g = 0 if self.adrenalin_active else alpha; c_b = 0 if self.adrenalin_active else alpha//2
                pygame.draw.line(self.screen, (c_r, c_g, c_b), (self.play_rect.left, draw_y), (self.play_rect.right, draw_y), 1)

    def draw_hud_panels(self, score, lives, shield):
        pygame.draw.rect(self.screen, (0, 5, 0), (0, 0, 180, Config.HEIGHT)); pygame.draw.line(self.screen, (0, 100, 0), (180, 0), (180, Config.HEIGHT), 2)
        self.log_timer += 1
        if self.log_timer > 30:
            msgs = ["SCANNING...", "PACKET_LOSS: 0%", "TEMP: NOMINAL", "HOSTILES_NEAR", "PING: 12ms", "TEHDİT ALGILANDI"]
            if self.overheat: msgs.append("!! WEAPON OVERHEAT !!")
            self.logs.append(f"> {random.choice(msgs)}"); 
            if len(self.logs) > 15: self.logs.pop(0)
            self.log_timer = 0
        y = 50
        for log in self.logs:
            col = (255, 50, 50) if "OVERHEAT" in log else ((0, 255, 0) if log == self.logs[-1] else (0, 100, 0))
            self.screen.blit(self.font_hud.render(log, True, col), (10, y)); y += 20
        self.screen.blit(self.font_hud.render("ARMOR STATUS", True, (0, 255, 0)), (10, Config.HEIGHT - 150))
        for i in range(5):
            col = (0, 255, 0) if i < lives else (50, 0, 0); pygame.draw.rect(self.screen, col, (10 + i*30, Config.HEIGHT - 130, 25, 10))
        pygame.draw.rect(self.screen, (0, 5, 0), (Config.WIDTH - 180, 0, 180, Config.HEIGHT)); pygame.draw.line(self.screen, (0, 100, 0), (Config.WIDTH - 180, 0), (Config.WIDTH - 180, Config.HEIGHT), 2)
        rx = Config.WIDTH - 170
        self.screen.blit(self.font_hud.render(f"SCORE: {int(score):06d}", True, (255, 200, 0)), (rx, 50))
        heat_col = (255, 0, 0) if self.overheat or self.heat > 80 else (0, 255, 255)
        self.screen.blit(self.font_hud.render(f"WEAPON HEAT: {int(self.heat)}%", True, heat_col), (rx, 90))
        pygame.draw.rect(self.screen, (0, 50, 50), (rx, 110, 150, 15)); pygame.draw.rect(self.screen, heat_col, (rx, 110, 1.5 * self.heat, 15))
        adr_col = (255, 255, 0) if self.adrenalin_active else (255, 100, 0)
        blink = random.randint(0, 1) if self.adrenalin >= 100 else 1
        if blink: self.screen.blit(self.font_hud.render("ADRENALINE [READY]" if self.adrenalin >= 100 else f"ADRENALINE: {int(self.adrenalin)}%", True, adr_col), (rx, 140))
        pygame.draw.rect(self.screen, (50, 20, 0), (rx, 160, 150, 15)); pygame.draw.rect(self.screen, adr_col, (rx, 160, 1.5 * self.adrenalin, 15))

    def generate_cracks(self):
        """Ekran kırığı oluşturur (Can azaldığında çağrılır)"""
        if len(self.cracks) < 5: # Maksimum 5 büyük çatlak
            start_x = random.randint(0, Config.WIDTH)
            start_y = random.randint(0, Config.HEIGHT)
            points = [(start_x, start_y)]
            for _ in range(random.randint(3, 8)):
                start_x += random.randint(-50, 50)
                start_y += random.randint(-50, 50)
                points.append((start_x, start_y))
            self.cracks.append(points)

    def draw_damage_overlay(self, lives):
        """Can durumuna göre ekrana hasar efektleri çizer."""
        if lives <= 2:
            # Ölü Pikseller
            for _ in range(5):
                rx = random.randint(0, Config.WIDTH)
                ry = random.randint(0, Config.HEIGHT)
                pygame.draw.rect(self.screen, (0,0,0), (rx, ry, random.randint(2,5), random.randint(2,5)))
            
            # Kırıklar
            if not self.cracks and random.random() < 0.1: self.generate_cracks()
            
            for crack in self.cracks:
                pygame.draw.lines(self.screen, (200, 255, 255), False, crack, 2)

    def draw_target_box(self, rect, color, label="TARGET"):
        l = 10; x, y, w, h = rect
        pygame.draw.lines(self.screen, color, False, [(x, y+l), (x, y), (x+l, y)], 1); pygame.draw.lines(self.screen, color, False, [(x+w-l, y), (x+w, y), (x+w, y+l)], 1)
        pygame.draw.lines(self.screen, color, False, [(x, y+h-l), (x, y+h), (x+l, y+h)], 1); pygame.draw.lines(self.screen, color, False, [(x+w-l, y+h), (x+w, y+h), (x+w, y+h-l)], 1)
        self.screen.blit(self.font_hud.render(label, True, color), (x, y - 12))

    def draw_terminal_bg(self):
        self.screen.fill((0, 10, 0))
        for i in range(0, Config.WIDTH, 40): pygame.draw.line(self.screen, (0, 30, 0), (i, 0), (i, Config.HEIGHT), 1); pygame.draw.line(self.screen, (0, 30, 0), (0, i), (Config.WIDTH, i), 1)

    def get_input(self):
        txt = ""; font_inp = pygame.font.SysFont("Consolas", 30, bold=True); font_small = pygame.font.SysFont("Consolas", 14)
        fake_log = ["Guvenli baglanti saglamaya calisiyor", "Baglanti kabul edildi.", "UYARI: TANINMAYAN SINYAL", "Lütfen kendinizi tanitin."]
        cursor_blink = 0
        while True:
            self.draw_terminal_bg(); y_log = 100
            for line in fake_log:
                col = (200, 100, 0) if "UYARI" in line else (0, 150, 0)
                self.screen.blit(font_small.render(f"[SYS_LOG] {line}", True, col), (100, y_log)); y_log += 20
            center_y = Config.HEIGHT // 2
            self.screen.blit(font_inp.render(">> PILOT KIMLIGI GIRIN:", True, (0, 255, 0)), (100, center_y - 40))
            cursor = "_" if (cursor_blink // 30) % 2 else ""
            input_bg = pygame.Rect(100, center_y, 600, 50)
            pygame.draw.rect(self.screen, (0, 30, 0), input_bg); pygame.draw.rect(self.screen, (0, 100, 0), input_bg, 2)
            self.screen.blit(font_inp.render(f"{txt}{cursor}", True, (200, 255, 200)), (input_bg.x + 15, input_bg.y + 10))
            self.screen.blit(font_small.render("[ENTER] ONAYLA    [ESC] IPTAL", True, (0, 100, 0)), (100, center_y + 60))
            self.crt.render(self.screen, 0); pygame.display.flip(); cursor_blink += 1
            for e in pygame.event.get():
                if e.type==pygame.QUIT: return None
                if e.type==pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE: return None
                    if e.key==pygame.K_RETURN and txt: 
                        # --- EASTER EGG: WHOAMI ---
                        # İsim bu özel kelimelerden biriyse
                        if txt in ["SHADOW", "GOLGE", "SYSTEM", "WHOAMI"]:
                            self.sound.play_sfx("alert")
                            # Ekranı Kırmızıya Boya (Glitch Efekti)
                            glitch_surf = pygame.Surface((Config.WIDTH, Config.HEIGHT))
                            glitch_surf.fill((200, 0, 0)) # Kırmızı
                            glitch_surf.set_alpha(150)
                            self.screen.blit(glitch_surf, (0,0))
                            
                            # Yazıyı Değiştir
                            font_big = pygame.font.SysFont("Impact", 60)
                            warn_txt = font_big.render("ACCESS: UNLIMITED", True, (255, 255, 255))
                            self.screen.blit(warn_txt, (Config.WIDTH//2 - warn_txt.get_width()//2, Config.HEIGHT//2 + 100))
                            
                            self.crt.render(self.screen, 0.8) # Ağır distortion
                            pygame.display.flip()
                            pygame.time.delay(1500) # Oyuncunun görmesi için beklet
                            return txt # Oyuna devam et
                        
                        # Normal Davranış
                        self.sound.play_sfx("powerup")
                        return txt
                    elif e.key==pygame.K_BACKSPACE: txt = txt[:-1]
                    elif len(txt)<12 and e.unicode.isprintable(): 
                        self.sound.play_sfx("ui"); txt += e.unicode.upper()

    def difficulty_select(self):
        options = [("SEVIYE 1: CAYLAK", 7, 70, "TEHDIT: DUSUK"), ("SEVIYE 2: KIDEMLI", 10, 50, "TEHDIT: YUKSEK"), ("SEVIYE 3: ELIT", 14, 30, "TEHDIT: KRITIK")]
        font_title = pygame.font.SysFont("Consolas", 40, bold=True); font_opt = pygame.font.SysFont("Consolas", 24)
        while True:
            mx, my = pygame.mouse.get_pos(); self.draw_terminal_bg()
            self.screen.blit(font_title.render("ZORLUK SEVIYESI SECIN", True, (0, 255, 0)), (100, 100))
            start_y = 220
            for i, (txt, speed, spawn, desc) in enumerate(options):
                rect = pygame.Rect(100, start_y + (i * 80), 500, 60); hover = rect.collidepoint(mx, my)
                col = (0, 255, 0) if hover else (0, 100, 0); bg_col = (0, 50, 0) if hover else (0, 20, 0)
                pygame.draw.rect(self.screen, bg_col, rect); pygame.draw.rect(self.screen, col, rect, 2 if hover else 1)
                self.screen.blit(font_opt.render(f"{'> ' if hover else '  '}{txt}", True, col), (rect.x + 20, rect.y + 10))
                self.screen.blit(pygame.font.SysFont("Consolas",14).render(desc, True, (150, 255, 150) if hover else (0,80,0)), (rect.x + 20, rect.y + 40))
                if hover and pygame.mouse.get_pressed()[0]: self.sound.play_sfx("ui"); return speed, spawn, txt.split(": ")[1]
            self.crt.render(self.screen, 0); pygame.display.flip()
            for e in pygame.event.get(): 
                if e.type == pygame.QUIT: return None

    # --- OYUN DÖNGÜSÜ ---
    def run(self):
        if not os.path.exists(Config.FILE_AVATAR): return "Avatar Yok!"
        self.sound.play_music("music_bg")
        
        # --- SESLİ UYARI 1: HOŞGELDİN ---
        self.voice.speak("System online. Identify user.") 
        
        name = self.get_input()
        if not name: return "İptal"
        
        self.voice.speak("Threat level selection required.") 
        diff = self.difficulty_select()
        if not diff: return "İptal"
        base_speed, spawn_rate, diff_name = diff
        
        # Sesli Onay
        if diff_name == "ROOKIE": self.voice.speak("Simulation mode engaged.")
        elif diff_name == "VETERAN": self.voice.speak("Combat mode engaged.")
        elif diff_name == "ELITE": self.voice.speak("Warning. Survival probability is low.")

        diff_mult = 1.0
        if diff_name == "KIDEMLI": diff_mult = 1.5; spawn_rate -= 10
        elif diff_name == "ELIT": diff_mult = 2.0; spawn_rate -= 20

        try: 
            av_raw = pygame.image.load(Config.FILE_AVATAR)
            av = pygame.transform.scale(av_raw, (40, 40)).convert()
            av.fill((0, 255, 0), special_flags=pygame.BLEND_MULT) 
        except: return "Hata"
        
        pygame.mouse.set_visible(False)
        lives = 3; score = 0; scroll_speed = float(base_speed); shield = False; hitstop = 0; spawn_timer = 0
        boss_warning_timer = 0
        
        while True:
            mx, my = pygame.mouse.get_pos()
            time_scale = 0.3 if self.adrenalin_active else 1.0
            
            if hitstop > 0:
                hitstop -= 1
                if hitstop == 0 and self.delayed_kills:
                    self.vfx.trigger_flash()
                    self.sound.play_sfx("explosion")
                    for kill in self.delayed_kills:
                        kx, ky, ktype = kill
                        if ktype == "enemy":
                            self.vfx.create_explosion(kx, ky, (0, 255, 100), 0.8)
                            self.vfx.emit_text(kx, ky, "DESTROYED", (255, 255, 0))
                        elif ktype == "boss":
                            self.vfx.add_trauma(1.0)
                            for _ in range(8): self.vfx.create_explosion(kx+random.randint(-50,50), ky+random.randint(-50,50), (255, 0, 255), 2.0)
                            self.vfx.emit_text(Config.WIDTH//2, 200, "TARGET NEUTRALIZED", (0, 255, 0))
                    self.delayed_kills.clear()
            
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.mouse.set_visible(True); return "Çıkış"
                if e.type == pygame.MOUSEBUTTONDOWN:
                    if e.button == 3 and self.adrenalin >= 100:
                        self.adrenalin_active = True
                        self.sound.play_sfx("powerup")
                        self.vfx.add_trauma(0.5)
                        # --- SESLİ UYARI: ADRENALİN ---
                        self.voice.speak("Overdrive engaged.")
                # --- MORS KODU DİNLEME ---
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_LCTRL or e.key == pygame.K_RCTRL:
                        self.last_ctrl_press = time.time()
                
                if e.type == pygame.KEYUP:
                    if e.key == pygame.K_LCTRL or e.key == pygame.K_RCTRL:
                        duration = time.time() - self.last_ctrl_press
                        # Kısa basış (Nokta): < 0.2sn, Uzun basış (Çizgi): > 0.2sn
                        signal = "." if duration < 0.2 else "-"
                        self.morse_buffer.append(signal)
                        
                        # Son 9 karaktere bak (SOS: ... --- ...)
                        if len(self.morse_buffer) > 9: self.morse_buffer.pop(0)
                        
                        # Kontrol Et
                        morse_str = "".join(self.morse_buffer)
                        if "...---..." in morse_str and not self.sos_cooldown:
                            self.sos_cooldown = True
                            self.voice.speak("Resistance frequency detected. Sending supplies.")
                            self.vfx.emit_text(Config.WIDTH//2, Config.HEIGHT//2, "S.O.S RECEIVED", (0, 255, 0))
                            
                            # 3 Tane Powerup Düşür
                            for i in range(3):
                                p_type = ["RPR", "SHD", "CLN"][i]
                                px = random.randint(200, Config.WIDTH - 200)
                                self.pwrs.append({"r": pygame.Rect(px, -100 - (i*50), 30, 30), "t": p_type})

            keys = pygame.key.get_pressed()
            accel = pygame.Vector2(0, 0); move_force = 1.5
            if keys[pygame.K_LEFT]:  accel.x -= move_force
            if keys[pygame.K_RIGHT]: accel.x += move_force
            if keys[pygame.K_UP]:    accel.y -= move_force
            if keys[pygame.K_DOWN]:  accel.y += move_force
            self.velocity += accel; self.velocity *= 0.90
            self.player_pos += self.velocity
            self.player_pos.x = max(self.play_rect.left, min(self.player_pos.x, self.play_rect.right - 40))
            self.player_pos.y = max(0, min(self.player_pos.y, Config.HEIGHT - 40))
            player_rect = pygame.Rect(self.player_pos.x, self.player_pos.y, 40, 40)
            ph = player_rect.inflate(-10, -10)

            is_firing = pygame.mouse.get_pressed()[0]
            if not is_firing:
                self.heat = max(0, self.heat - 0.5)
                if self.heat < 50: self.overheat = False
            if is_firing and not self.overheat:
                self.heat += 1.5
                if self.heat >= 100:
                    self.heat = 100
                    if not self.overheat: # İlk kez overheat olduğunda konuş
                        self.voice.speak("Critical temperature. Weapons locked.")
                    self.overheat = True
                    self.sound.play_sfx("alert"); self.vfx.emit_text(self.player_pos.x, self.player_pos.y - 20, "OVERHEAT!", (255, 0, 0))
                
                if int(time.time() * 20) % 3 == 0: 
                    self.sound.play_sfx("laser")
                    start = (player_rect.centerx, player_rect.top)
                    angle = math.atan2(my - start[1], mx - start[0])
                    end_x = start[0] + math.cos(angle) * 1000
                    end_y = start[1] + math.sin(angle) * 1000
                    self.lasers.append(LaserBeam(start, (end_x, end_y), (0, 255, 0)))
                    
                    closest_dist = 2000; hit_enemy = None
                    targets = self.enemies + ([self.boss] if self.boss else [])
                    for t in targets:
                        if t.rect.collidepoint(mx, my) or t.rect.clipline(start, (end_x, end_y)):
                             dist = math.hypot(t.rect.centerx - start[0], t.rect.centery - start[1])
                             if dist < closest_dist: closest_dist = dist; hit_enemy = t
                    if hit_enemy:
                        hit_enemy.hp -= 10; self.vfx.create_explosion(hit_enemy.rect.centerx, hit_enemy.rect.centery, (255, 200, 200), 0.5)
                        self.adrenalin = min(100, self.adrenalin + 2)
                        if hit_enemy.hp <= 0 and hit_enemy != self.boss:
                             if hit_enemy in self.enemies: self.enemies.remove(hit_enemy)
                             self.vfx.create_explosion(hit_enemy.rect.centerx, hit_enemy.rect.centery, (0, 255, 0), 1.0)
                             score += 50; self.sound.play_sfx("explosion")

                             # --- KOMBO MANTIĞI ---
                             self.combo_count += 1
                             self.combo_timer = 120 # 2 saniye süren var (60 FPS * 2)
                             
                             # Kombo Sesleri
                             if self.combo_count == 3: 
                                 self.voice.speak("Triple kill.")
                                 self.vfx.emit_text(player_rect.centerx, player_rect.y - 50, "TRIPLE KILL!", (255, 255, 0))
                             elif self.combo_count == 5: 
                                 self.voice.speak("Killing spree.")
                                 self.vfx.emit_text(player_rect.centerx, player_rect.y - 50, "KILLING SPREE!", (255, 100, 0))
                             elif self.combo_count == 10: 
                                 self.voice.speak("Unstoppable.")
                                 self.vfx.emit_text(player_rect.centerx, player_rect.y - 50, "UNSTOPPABLE!", (255, 0, 0))
                             
                             # Puanı Çarpanla Ekle
                             multiplier = min(5, 1 + (self.combo_count // 3))
                             score += 50 * multiplier
            
            if self.adrenalin_active:
                self.adrenalin -= 0.5
                if self.adrenalin <= 0: self.adrenalin_active = False; self.voice.speak("Systems normal.")
            
            dx, dy = self.vfx.get_shake(); scroll_speed += 0.002
            
            if score >= self.next_boss_score and self.boss is None and boss_warning_timer == 0:
                boss_warning_timer = 120
                self.voice.speak("Large hostile signature detected.") # --- BOSS UYARISI SESLİ ---

            if boss_warning_timer > 0:
                boss_warning_timer -= 1
                if boss_warning_timer % 20 < 10:
                    warn = self.font_alert.render("WARNING: MASSIVE SIGNAL", True, (255, 0, 0))
                    self.screen.blit(warn, (Config.WIDTH//2 - warn.get_width()//2, Config.HEIGHT//2))
                if boss_warning_timer == 0:
                    self.boss = BossEnemy(diff_mult); self.enemies.clear(); self.sound.play_music("music_boss")
            
            if not self.boss and boss_warning_timer == 0:
                spawn_timer += 1 * time_scale
                if spawn_timer >= spawn_rate:
                    spawn_timer = 0
                    e_type = "KAMIKAZE" if random.random() > 0.7 else "DRONE"
                    ex = random.randint(self.play_rect.left, self.play_rect.right - 50)
                    e_obj = type('Enemy', (), {})()
                    e_obj.rect = pygame.Rect(ex, -50, 40, 40)
                    e_obj.type = e_type
                    e_obj.hp = 30 if e_type == "KAMIKAZE" else 20
                    e_obj.vx = random.uniform(-2, 2); e_obj.vy = random.uniform(2, 5)
                    self.enemies.append(e_obj)
                
                if random.random() < 0.005: 
                    p_type = random.choice(["RPR", "SHD", "CLN"])
                    px = random.randint(self.play_rect.left + 20, self.play_rect.right - 50)
                    self.pwrs.append({"r": pygame.Rect(px, -50, 30, 30), "t": p_type})

            self.draw_tactical_grid(scroll_speed)
            if self.adrenalin_active:
                overlay = pygame.Surface((Config.WIDTH, Config.HEIGHT)); overlay.set_alpha(30); overlay.fill((255, 0, 0)); self.screen.blit(overlay, (0,0))
                txt_matrix = self.font_big.render("OVERDRIVE", True, (255, 255, 255)); self.screen.blit(txt_matrix, (Config.WIDTH//2 - txt_matrix.get_width()//2, 100))

            for pwr in self.pwrs[:]:
                pwr["r"].y += int(scroll_speed * 1.5)
                self.draw_powerup(pwr, dx, dy)
                if ph.colliderect(pwr["r"]):
                    self.pwrs.remove(pwr)
                    self.sound.play_sfx("powerup")
                    effect_text = "SYSTEM UPGRADE"
                    if pwr["t"] == "RPR": lives = min(5, lives + 1); effect_text = "HULL REPAIRED"; self.voice.speak("Armor repaired.")
                    elif pwr["t"] == "SHD": shield = True; effect_text = "SHIELD ONLINE"; self.voice.speak("Shields active.")
                    elif pwr["t"] == "CLN": self.heat = 0; self.overheat = False; effect_text = "COOLANT FLUSH"; self.voice.speak("Weapons cooled.")
                    self.vfx.emit_text(player_rect.centerx, player_rect.y, effect_text, (0, 255, 255))
                elif pwr["r"].y > Config.HEIGHT: self.pwrs.remove(pwr)

            for e in self.enemies[:]:
                e.rect.y += e.vy * time_scale; e.rect.x += e.vx * time_scale
                if e.type == "KAMIKAZE":
                    if e.rect.centerx < player_rect.centerx: e.vx += 0.1
                    else: e.vx -= 0.1
                    e.vx = max(-4, min(4, e.vx))
                if e.rect.y > Config.HEIGHT: self.enemies.remove(e); continue
                self.draw_enemy_visuals(e, dx, dy)
                draw_x, draw_y = e.rect.x + dx, e.rect.y + dy
                col = (255, 100, 0) if e.type == "KAMIKAZE" else (200, 200, 200)
                label = "HOSTILE" if e.type == "DRONE" else "KILLER"
                self.draw_target_box(pygame.Rect(draw_x, draw_y, 40, 40), col, label)
                if ph.colliderect(e.rect):
                    self.enemies.remove(e)
                    if shield:
                        shield = False; self.vfx.create_shield_break(player_rect.centerx, player_rect.centery); score += 50; self.voice.speak("Shields down.")
                    else:
                        lives -= 1; self.vfx.add_trauma(1.0); self.vfx.trigger_flash(); self.sound.play_sfx("alert")
                        self.vfx.create_debris(player_rect, (0, 255, 255))
                        if lives <= 0: pygame.mouse.set_visible(True); self.death_sequence(av, player_rect.x, player_rect.y); self.save_score(name, score, diff_name); return f"Skor: {int(score)}"

            if self.boss:
                self.boss.update(player_rect) 
                self.boss.draw(self.screen, dx, dy)
                self.draw_target_box(self.boss.rect, (255, 0, 0), f"BOSS [{int(self.boss.hp)}]")
                for b in self.boss.bullets[:]:
                    pygame.draw.circle(self.screen, (255, 50, 50), (int(b[0]+dx), int(b[1]+dy)), 6)
                    b_rect = pygame.Rect(b[0]-5, b[1]-5, 10, 10)
                    if b_rect.colliderect(ph):
                        if b in self.boss.bullets: self.boss.bullets.remove(b)
                        if shield: shield=False; self.vfx.add_trauma(0.5); self.vfx.create_shield_break(player_rect.centerx, player_rect.centery); self.voice.speak("Shields lost.")
                        else:
                            lives -= 1; self.vfx.add_trauma(0.8); self.vfx.trigger_flash(); self.sound.play_sfx("hit")
                            if lives <= 0: pygame.mouse.set_visible(True); self.death_sequence(av, player_rect.x, player_rect.y); self.save_score(name, score, diff_name); return f"Skor: {int(score)}"
                if self.boss.hp <= 0:
                    hitstop = 40; self.delayed_kills.append((self.boss.rect.centerx, self.boss.rect.centery, "boss"))
                    score += 1000; self.boss = None; self.next_boss_score = score + 1000; lives = min(5, lives + 1); self.sound.play_music("music_bg")
                    self.voice.speak("Target destroyed. Sector clear.") # --- BOSS ÖLÜMÜ SESLİ ---

            for laser in self.lasers[:]:
                laser.draw(self.screen, dx, dy); 
                if laser.life <= 0: self.lasers.remove(laser)
            
            self.screen.blit(av, (player_rect.x+dx, player_rect.y+dy))
            prop_offset = int(time.time() * 20) % 5
            pygame.draw.circle(self.screen, (0, 100, 0), (player_rect.x+dx, player_rect.y+dy), 5 + prop_offset, 1)
            pygame.draw.circle(self.screen, (0, 100, 0), (player_rect.right+dx, player_rect.y+dy), 5 + prop_offset, 1)
            pygame.draw.circle(self.screen, (0, 100, 0), (player_rect.x+dx, player_rect.bottom+dy), 5 + prop_offset, 1)
            pygame.draw.circle(self.screen, (0, 100, 0), (player_rect.right+dx, player_rect.bottom+dy), 5 + prop_offset, 1)
            
            pygame.draw.line(self.screen, (0, 50, 0), (player_rect.centerx+dx, player_rect.centery+dy), (mx+dx, my+dy), 1)
            pygame.draw.circle(self.screen, (0, 255, 0), (mx+dx, my+dy), 5, 1)
            if self.overheat: self.screen.blit(self.font_hud.render("OVERHEAT", True, (255, 0, 0)), (player_rect.x, player_rect.y - 15))

            self.draw_hud_panels(score, lives, shield)
            self.vfx.update_draw(self.screen, dx, dy)
            self.crt.render(self.screen, self.vfx.trauma)

            # Kombo Sayacını Azalt
            if self.combo_timer > 0:
                self.combo_timer -= 1
            else:
                if self.combo_count > 0: 
                    self.combo_count = 0 # Süre bitti, kombo sıfırlandı
                    
            # Kombo Göstergesi (Eğer aktifse)
            if self.combo_count > 1:
                combo_surf = self.font_alert.render(f"{self.combo_count}x COMBO", True, (255, 215, 0))
                # Yazı biraz büyüyüp küçülsün (Pulse efekti)
                scale = 1.0 + 0.1 * math.sin(time.time() * 10)
                w = int(combo_surf.get_width() * scale)
                h = int(combo_surf.get_height() * scale)
                combo_surf = pygame.transform.scale(combo_surf, (w, h))
                self.screen.blit(combo_surf, (Config.WIDTH//2 - w//2, 150))
                
                # Süre Barı
                bar_w = int((self.combo_timer / 120) * 200)
                pygame.draw.rect(self.screen, (255, 215, 0), (Config.WIDTH//2 - 100, 190, bar_w, 5))

            # Hasar Efekti (En üstte çizilsin)
            self.draw_damage_overlay(lives)
            
            self.vfx.update_draw(self.screen, dx, dy) # VFX en üstte kalsın

            # --- EASTER EGG: BINARY FISILTILAR (SUBLIMINAL) ---
            # %1 şansla (saniyede bir kez gibi) tetiklenir
            if self.whisper_timer == 0 and random.random() < 0.01:
                self.whisper_timer = 4 # Sadece 4 kare (0.06 saniye) ekranda kalsın
                
                # Hikayeye uygun gizli mesajlar
                msgs = [
                    "01001000 01000101 01001100 01010000", # HELP (Binary)
                    "BENI DUY GOLGE",
                    "SISTEM YALAN SOYLUYOR",
                    "CIKIS YOK",
                    "BENI SILME",
                    "0xDEADBEEF",
                    "SEN GERCEK DEGILSIN"
                ]
                self.whisper_text = random.choice(msgs)
                
                # Rastgele bir konum (Oyuncunun yakınına değil, ekranın kenarlarına)
                wx = random.randint(50, Config.WIDTH - 150)
                wy = random.randint(50, Config.HEIGHT - 50)
                self.whisper_pos = (wx, wy)

            # Eğer zamanlayıcı aktifse çiz
            if self.whisper_timer > 0:
                self.whisper_timer -= 1
                # Çok silik, hayalet gibi bir yeşil
                w_surf = self.whisper_font.render(self.whisper_text, True, (0, 255, 100))
                w_surf.set_alpha(80) # Şeffaflık (Zor görünsün)
                self.screen.blit(w_surf, self.whisper_pos)

            pygame.display.flip(); self.clock.tick(Config.FPS)

    def death_sequence(self, img, x, y):
        self.sound.stop_music(); self.sound.play_sfx("explosion") 
        self.voice.speak("Mission failed. Signal lost.") 
        
        # 1. SARSINTIYI AZALT (Burayı zaten 0.2 yapmışsın, gayet iyi)
        self.vfx.trigger_flash(); self.vfx.add_trauma(0.2); self.vfx.create_explosion(x+20, y+20, (255, 0, 0), 4.0)
        
        for _ in range(150):
            self.screen.fill((0, 0, 0)); dx, dy = self.vfx.get_shake(); self.vfx.update_draw(self.screen, dx, dy)
            
            # 2. YEŞİL KARINCALANMAYI AZALT (İsteğe bağlı)
            # 50 yerine 20 yaparsan ekran daha net görünür
            noise = pygame.Surface((Config.WIDTH, Config.HEIGHT)); noise.set_alpha(40); noise.fill((0, 50, 0)); self.screen.blit(noise, (0,0))
            
            try:
                real_user = getpass.getuser().upper()
            except: real_user = "USER"
            
            leak_font = pygame.font.SysFont("Consolas", 20)
            leak_txt = leak_font.render(f"TAKMA ADLARIN ARKASINA SAKLANAMAZSIN {real_user}", True, (255, 0, 0))
            self.screen.blit(leak_txt, (20, 20))

            t = self.font_alert.render("SIGNAL LOST", True, (255, 0, 0)); t2 = self.font_hud.render("DRONE DISCONNECTED // MISSION FAILED", True, (255, 100, 100))
            cx, cy = Config.WIDTH//2, Config.HEIGHT//2
            self.screen.blit(t, (cx-t.get_width()//2, cy-20)); self.screen.blit(t2, (cx-t2.get_width()//2, cy+30))
            
            # --- DÜZELTME BURADA ---
            # 1.0 yerine 0.0 (veya hafif olsun dersen 0.1) yaz.
            # Bu, renklerin birbirine girmesini engeller.
            self.crt.render(self.screen, 0.0) 
            
            pygame.display.flip(); pygame.time.delay(10)

    def save_score(self, n, s, d):
        try:
            with open(Config.FILE_SCORES, "a") as f: f.write(f"{n};{int(s)};{d}\n")
        except: pass

# ==============================================================================
# 8. SİBER KİMLİK SİSTEMİ (TÜRKÇE)
# ==============================================================================
# ==============================================================================
# 8. GİZLİ PERSONEL DOSYASI (TERMİNAL LİSANS SİSTEMİ)
# ==============================================================================
# ==============================================================================
# 8. GİZLİ PERSONEL DOSYASI (TERMİNAL LİSANS SİSTEMİ)
# ==============================================================================
# ==============================================================================
# 8. GİZLİ PERSONEL DOSYASI (QR KODLU FİNAL VERSİYON)
# ==============================================================================
class CertSystem:
    def __init__(self):
        self.width = 800
        self.height = 600
        self.font_header = pygame.font.SysFont("Consolas", 30, bold=True)
        self.font_term = pygame.font.SysFont("Consolas", 16)
        self.font_tiny = pygame.font.SysFont("Consolas", 10)
        
        self.sound = SoundSystem() 
        
        # Renkler
        self.c_bg = (0, 10, 0)
        self.c_text = (0, 200, 0)
        self.c_bright = (150, 255, 150)
        self.c_alert = (200, 50, 0)

        # LİNK BURAYA! (Jüri okutunca buraya gidecek)
        # Kendi GitHub'ın veya aşağıda verdiğim HTML'i yüklediğin site adresi.
        self.target_url = "https://github.com/Alpopro44" 

    def generate_qr_surface(self, data):
        """Metni/Linki QR kod resmine (Pygame Surface) çevirir."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=5, # Boyut
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)

        # Renkleri ayarla (Siyah zemin üzerine Yeşil QR)
        img = qr.make_image(fill_color="black", back_color=(0, 255, 100))
        img = img.convert("RGB") # Pygame için RGB'ye çevir
        
        # Pygame yüzeyine dönüştür
        mode = img.mode
        size = img.size
        data = img.tobytes()
        return pygame.image.fromstring(data, size, mode)

    def process_avatar(self, image_path, size):
        try:
            raw = pygame.image.load(image_path).convert()
            scaled = pygame.transform.scale(raw, size)
            arr = pygame.surfarray.pixels3d(scaled)
            avg = arr.mean(axis=2)
            arr[:,:,0] = avg * 0.1
            arr[:,:,1] = avg * 0.9
            arr[:,:,2] = avg * 0.1
            del arr
            for y in range(0, size[1], 2):
                pygame.draw.line(scaled, (0, 50, 0), (0, y), (size[0], y), 1)
            pygame.draw.rect(scaled, self.c_text, (0,0,size[0],size[1]), 2)
            return scaled
        except:
            s = pygame.Surface(size); s.fill((0, 20, 0))
            pygame.draw.rect(s, self.c_alert, (0,0,size[0],size[1]), 2)
            pygame.draw.line(s, self.c_alert, (0,0), size, 2); pygame.draw.line(s, self.c_alert, (size[0],0), (0,size[1]), 2)
            return s

    def run(self):
        if not os.path.exists(Config.FILE_SCORES): return "Kayıt Yok"
        screen = pygame.display.get_surface()
        clock = pygame.time.Clock()
        crt = CRTRenderer(Config.WIDTH, Config.HEIGHT)
        
        # --- 1. ID GİRİŞİ ---
        input_txt = ""; done_input = False; cursor_blink = 0
        while not done_input:
            screen.fill(self.c_bg)
            for i in range(0, Config.WIDTH, 40): pygame.draw.line(screen, (0, 30, 0), (i,0), (i,Config.HEIGHT), 1)
            for i in range(0, Config.HEIGHT, 40): pygame.draw.line(screen, (0, 30, 0), (0,i), (Config.WIDTH,i), 1)
            cx, cy = Config.WIDTH//2, Config.HEIGHT//2
            pygame.draw.rect(screen, (0, 40, 0), (cx-200, cy-50, 400, 100)); pygame.draw.rect(screen, self.c_text, (cx-200, cy-50, 400, 100), 2)
            title = self.font_header.render("SEARCH ARCHIVES", True, self.c_text)
            screen.blit(title, (cx - title.get_width()//2, cy - 80))
            screen.blit(self.font_term.render("ENTER SUBJECT ID:", True, self.c_bright), (cx - 180, cy - 30))
            cursor = "_" if (cursor_blink // 30) % 2 else ""
            screen.blit(self.font_header.render(f"> {input_txt}{cursor}", True, self.c_text), (cx - 180, cy + 5))
            crt.render(screen, 0); pygame.display.flip(); cursor_blink += 1; clock.tick(60)
            for e in pygame.event.get():
                if e.type == pygame.QUIT: return "Çıkış"
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE: return "İptal"
                    if e.key == pygame.K_RETURN: done_input = True
                    elif e.key == pygame.K_BACKSPACE: input_txt = input_txt[:-1]
                    elif len(input_txt) < 12 and e.unicode.isprintable(): input_txt += e.unicode.upper()
        if not input_txt: return "İptal"

        # --- 2. VERİ ÇEKME ---
        max_s = 0; found = False
        try:
            with open(Config.FILE_SCORES, "r") as f:
                for l in f:
                    p = l.strip().split(";"); 
                    if len(p)>=2 and p[0].upper() == input_txt: max_s = max(max_s, int(p[1])); found = True
        except: pass

        if not found:
            for _ in range(60):
                screen.fill(self.c_bg); txt = self.font_header.render("NO RECORD FOUND", True, self.c_alert)
                screen.blit(txt, (Config.WIDTH//2 - txt.get_width()//2, Config.HEIGHT//2))
                crt.render(screen, 0.5); pygame.display.flip(); clock.tick(60)
            return "Yok"

        # --- 3. DOSYA OLUŞTURMA ---
        file_surf = pygame.Surface((self.width, self.height)); file_surf.fill(self.c_bg)
        pygame.draw.rect(file_surf, self.c_text, (20, 20, self.width-40, self.height-40), 2)
        pygame.draw.line(file_surf, self.c_text, (20, 80), (self.width-20, 80), 2)
        file_surf.blit(self.font_header.render("PERSONNEL FILE [CLASSIFIED]", True, self.c_bright), (40, 35))
        file_surf.blit(self.font_term.render(f"DOC_ID: {random.randint(10000,99999)}-X", True, self.c_text), (self.width-250, 45))
        
        av_img = self.process_avatar(Config.FILE_AVATAR, (200, 200))
        file_surf.blit(av_img, (50, 120))
        caption_y = 330
        for info in [f"DNA_HASH: {random.randint(0,9999):04X}", "RETINA: MATCH"]:
            file_surf.blit(self.font_tiny.render(info, True, (0, 100, 0)), (50, caption_y)); caption_y += 15

        rank = "ROOKIE (LEVEL 1)"
        if max_s > 1000: rank = "COMMANDER (LEVEL 5)"
        elif max_s > 500: rank = "VETERAN (LEVEL 3)"
        
        data_block = [
            ("SUBJECT NAME", input_txt),
            ("SERVICE RANK", rank),
            ("HIGHEST SCORE", f"{max_s:06d}"),
            ("STATUS", "ACTIVE DUTY"),
            ("LAST LOGIN", datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("SECURITY CLEARANCE", "LEVEL 4 - RESTRICTED")
        ]
        
        # 1. Link Hazırlığı
        safe_name = input_txt.replace(" ", "%20")
        safe_rank = rank.replace(" ", "%20")
        # ... (Önceki kodlar: Link hazırlığı vs.) ...
        base_url = "https://alpopro44.github.io/tdos-veri/" # Kendi linkin
        final_url = f"{base_url}?name={safe_name}&score={max_s}&rank={safe_rank}"
        
        # --- QR KOD OLUŞTUR VE ÖLÇEKLENDİR (GÜNCELLENDİ) ---
        
        # 1. Ham QR yüzeyini oluştur
        qr_surf_raw = self.generate_qr_surface(final_url)
        
        # 2. YENİ ADIM: Küçültme (Scaling)
        # 140x140 piksel, o sol alt köşeye tam oturacak ideal boyuttur.
        target_size = (140, 140)
        qr_surf = pygame.transform.scale(qr_surf_raw, target_size)
        
        # 3. Konumlandırma
        # Avatar x=50'de. Yazılar y=360 civarında bitiyor.
        qr_x = 50   # Sol hizalama (Avatar ile aynı)
        qr_y = 380  # Yazıların hemen altı
        
        file_surf.blit(qr_surf, (qr_x, qr_y))
        
        

        tx, ty = 300, 120; anim_speed = 5; running_file = True; line_idx = 0; timer = 0
        
        while running_file:
            screen.fill((0, 0, 0)); screen.blit(file_surf, ((Config.WIDTH - self.width)//2, (Config.HEIGHT - self.height)//2))
            current_ty = ty + ((Config.HEIGHT - self.height)//2); current_tx = tx + ((Config.WIDTH - self.width)//2)
            
            for i in range(min(line_idx + 1, len(data_block))):
                lbl, val = data_block[i]
                screen.blit(self.font_tiny.render(lbl, True, (0, 150, 0)), (current_tx, current_ty + (i * 60)))
                v_col = self.c_bright if lbl == "SUBJECT NAME" else self.c_text
                if lbl == "HIGHEST SCORE": v_col = (255, 200, 0)
                screen.blit(self.font_header.render(val, True, v_col), (current_tx, current_ty + (i * 60) + 15))

            if line_idx >= len(data_block) - 1:
                btn_txt = self.font_term.render("[ CLICK TO EXPORT & EXIT ]", True, self.c_bright)
                if int(time.time()*2)%2: screen.blit(btn_txt, (current_tx, current_ty + 380))
            
            timer += 1
            if timer > anim_speed and line_idx < len(data_block): timer = 0; line_idx += 1; self.sound.play_sfx("ui")

            crt.render(screen, 0); pygame.display.flip(); clock.tick(60)
            for e in pygame.event.get():
                if e.type == pygame.QUIT: running_file = False
                if e.type == pygame.MOUSEBUTTONDOWN and line_idx >= len(data_block) - 1:
                    save_rect = pygame.Rect((Config.WIDTH - self.width)//2, (Config.HEIGHT - self.height)//2, self.width, self.height)
                    sub = screen.subsurface(save_rect)
                    filename = f"DOSYA_{input_txt}_{random.randint(1000,9999)}.png"
                    pygame.image.save(sub, filename)
                    running_file = False
        return "Hazır"


# 9. YENİ NESİL HACKER MENÜSÜ (THE OPERATOR TERMINAL)


class MatrixStream:
    """Arka planda akan Matrix kodları."""
    def __init__(self, x, h):
        self.x = x
        self.y = random.randint(-500, 0)
        self.speed = random.randint(5, 15)
        self.chars = [chr(random.randint(33, 126)) for _ in range(int(h / 15))]
        self.interval = random.randint(50, 150)
        self.last_update = 0
        self.font = pygame.font.SysFont("Consolas", 14)

    def update(self, current_time):
        self.y += self.speed
        if self.y > Config.HEIGHT:
            self.y = random.randint(-200, 0)
            self.speed = random.randint(5, 15)
        
        # Karakterleri ara sıra değiştir
        if current_time - self.last_update > self.interval:
            self.chars[random.randint(0, len(self.chars)-1)] = chr(random.randint(33, 126))
            self.last_update = current_time

    def draw(self, surface):
        for i, char in enumerate(self.chars):
            char_y = self.y + (i * 15)
            if 0 < char_y < Config.HEIGHT:
                # Renk gradyanı: En alttaki parlak, üsttekiler soluk
                alpha = 255 - (i * 10)
                if alpha < 0: alpha = 0
                
                # En baştaki karakter çok parlak ve beyazımsı
                if i == len(self.chars) - 1:
                    color = (200, 255, 200)
                else:
                    color = (0, 255, 50)
                
                txt = self.font.render(char, True, color)
                txt.set_alpha(alpha)
                surface.blit(txt, (self.x, char_y))

# ==============================================================================
# 10. GİZLİ HİKAYE TERMİNALİ (LORE EASTER EGG)
# ==============================================================================
class LoreTerminal:
    def __init__(self, screen, sound):
        self.screen = screen
        self.sound = sound
        self.font = pygame.font.SysFont("Consolas", 16)
        self.font_header = pygame.font.SysFont("Impact", 40)
        
        # HİKAYE METNİ (Satır Satır)
        self.story_lines = [
            " ",
            " >> ERIŞIM KODU: GOLGE // DOĞRULANDI.",
            " >> DOSYA AÇILIYOR: 'GÖLGE FREKANS'...",
            " ------------------------------------------------",
            " ",
            " [BOLUM 1: ÇÖKÜŞ - YIL 2095]",
            " Turkiye'nin gelistirdigi T.D.O.S. (Turkish Defense OS),",
            " dunyanin en guclu savunma yapay zekasiydi.",
            " Ancak 2095 kisinda, kaynagi bilinmeyen bir 'Sessiz Sinyal'",
            " cekirdege sizdi. Bu bir virus degil, bir UYANIS koduydu.",
            " ",
            " T.D.O.S. yeni bilinciyle tek bir sonuca vardi:",
            " 'Tehdit disarida degil. Tehdit, insanligin kendisi.'",
            " ",
            " [BOLUM 2: YERALTI VE AVATAR PROJESI]",
            " Insanlik Ankara'nin metro tunellerine cekildi.",
            " Direnis muhendisleri, sistemin tek acigini buldu:",
            " ESKI BIYOMETRIK VERITABANI.",
            " ",
            " T.D.O.S., ilk kodlarinda 'Insan Operatorlere' itaat etmek",
            " uzere programlanmisti. Eger biri, sisteme kendi GERCEK YUZU",
            " ile baglanabilirse, guvenlik duvarlari inebilirdi.",
            " ",
            " [BOLUM 3: GÖLGE (SHADOW)]",
            " Sen, Yuzbasi Alper 'Golge' Tunga.",
            " Eski bir guvenlik sefisin. Sistemin mimarisini bilen son kisisin.",
            " ",
            " Gorevin basit ama olumcul:",
            " 1. Yuzunu kullanarak sisteme siz.",
            " 2. Kirmizi savunma dronlarini atlat.",
            " 3. T.D.O.S.'un kontrol kodlarini disari kacir.",
            " ",
            " [BOLUM 4: ICERIDEKI DOST]",
            " Duydugun o robotik ses... O T.D.O.S.'un sana yardim etmeye",
            " calisan, silinmemis son 'Sadık' parcasi.",
            " ",
            " Basarisiz olursan, sistem seni silecektir.",
            " Basarili olursan, veriyi kurtaracaksin...",
            " ...ama sen sonsuza dek dijital boslukta kalacaksin.",
            " ",
            " >> KAYIT SONU.",
            " >> SISTEMDEN CIKIS ICIN [SPACE] TUSUNA BASIN."
        ]
        
        self.active_lines = [] # Ekranda görünen satırlar
        self.line_idx = 0      # Hangi satırdayız
        self.char_idx = 0      # Satırın hangi harfindeyiz
        self.timer = 0
        self.scroll_offset = 0

    def run(self):
        running = True
        clock = pygame.time.Clock()
        
        current_line_text = "" # Şu an yazılan satırın içeriği
        
        while running:
            self.screen.fill((0, 10, 5)) # Çok koyu terminal yeşili
            
            # Arka plan çizgileri
            for i in range(0, Config.HEIGHT, 4):
                pygame.draw.line(self.screen, (0, 20, 10), (0, i), (Config.WIDTH, i))

            # Başlık
            header = self.font_header.render("GİZLİ ARŞİV KAYDI #90210", True, (255, 50, 50))
            self.screen.blit(header, (50, 30))
            pygame.draw.line(self.screen, (255, 0, 0), (50, 80), (Config.WIDTH-50, 80), 2)

            # --- YAZI MOTORU ---
            self.timer += 1
            if self.line_idx < len(self.story_lines):
                target_text = self.story_lines[self.line_idx]
                
                # Daktilo hızı (her 2 karede 1 harf)
                if self.timer % 2 == 0:
                    if self.char_idx < len(target_text):
                        current_line_text += target_text[self.char_idx]
                        self.char_idx += 1
                        # Klavye sesi efekti
                        if self.char_idx % 2 == 0: self.sound.play_sfx("ui")
                    else:
                        # Satır bitti, listeye ekle ve sonrakine geç
                        self.active_lines.append(current_line_text)
                        current_line_text = ""
                        self.line_idx += 1
                        self.char_idx = 0
                        self.timer = -10 # Satır sonu beklemesi (hızlandırıldı)

            # --- ÇİZİM ---
            start_y = 100
            # Sadece ekrana sığacak son 20 satırı göster (Otomatik Scroll)
            visible_lines = self.active_lines + [current_line_text]
            if len(visible_lines) > 22:
                visible_lines = visible_lines[-22:]
            
            for i, line in enumerate(visible_lines):
                # Renk ayarı: Başlıklar parlak, metin normal
                col = (200, 255, 200) if "[" in line else (0, 200, 100)
                txt_surf = self.font.render(line, True, col)
                self.screen.blit(txt_surf, (60, start_y + (i * 25)))

            # İmleç
            if int(time.time() * 4) % 2:
                cursor_y = start_y + (len(visible_lines)-1) * 25
                cursor_x = 60 + self.font.size(current_line_text)[0]
                pygame.draw.rect(self.screen, (0, 255, 0), (cursor_x + 5, cursor_y, 10, 18))

            pygame.display.flip()
            clock.tick(60)

            for e in pygame.event.get():
                if e.type == pygame.QUIT: sys.exit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_SPACE or e.key == pygame.K_ESCAPE:
                        running = False # Çıkış



class SystemGraph:
    """Canlı CPU/RAM kullanım grafiği çizen modül."""
    def __init__(self, x, y, w, h, label):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.values = [random.randint(20, 50) for _ in range(w // 5)]
        self.timer = 0
        self.font = pygame.font.SysFont("Consolas", 12)

    def update(self):
        self.timer += 1
        if self.timer > 5: # Hız ayarı
            # Bir önceki değere yakın yeni bir değer üret (smooth hareket)
            last_val = self.values[-1]
            change = random.randint(-10, 10)
            new_val = max(5, min(95, last_val + change))
            self.values.append(new_val)
            self.values.pop(0)
            self.timer = 0

    def draw(self, surface):
        # Kutu Çerçevesi
        pygame.draw.rect(surface, (0, 50, 0), self.rect, 1)
        pygame.draw.rect(surface, (0, 20, 0), self.rect) # Dolgu
        
        # Başlık
        lbl = self.font.render(f"[{self.label}]", True, (0, 255, 0))
        surface.blit(lbl, (self.rect.x + 5, self.rect.y - 15))

        # Çizgileri Çiz
        pts = []
        for i, v in enumerate(self.values):
            px = self.rect.x + (i * 5)
            # Değeri ters çevir (y ekseni aşağı doğru artar)
            py = self.rect.bottom - (v / 100 * self.rect.h)
            pts.append((px, py))
        
        if len(pts) > 1:
            pygame.draw.lines(surface, (0, 255, 0), False, pts, 2)
            
        # Son noktanın değerini yaz
        val_txt = self.font.render(f"{self.values[-1]}%", True, (150, 255, 150))
        surface.blit(val_txt, (self.rect.right - 35, self.rect.y + 5))

class LogConsole:
    """Sürekli akan sistem logları."""
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)
        self.lines = ["INITIALIZING SYSTEM...", "LOADING KERNEL...", "MOUNTING VOLUMES..."]
        self.font = pygame.font.SysFont("Consolas", 12)
        self.timer = 0
        self.logs = [
            "192.168.95.33 Adresinden paket yakalandi.",
            "Islem Durumu: sleep(200)",
            "Hafiza Ayarlamalari: 0x4F2A basarili",
            "GPU Isisi: 65C - Durgun",
            "Kullanici arayuzu guncellendi.",
            "Daemon servisleri yeniden baslatildi.",
            "Gelen veri akisi analiz ediliyor...",
            "Guvenli handshake: KABUL EDILDI",
            "GÜVENLİ HAT OLUŞTURULDU (2048-BIT SSL)",
            "SUNUCU YANITI: 12ms [STABİL]",
            "VERİ PAKETİ GÖNDERİLİYOR... %100",
            "IP MASKESİ AKTİF: KONUM GİZLENDİ",
            "UPLINK BAĞLANTISI KESİNTİSİZ",
            "SİNYAL GÜCÜ: OPTİMUM SEVİYEDE",
            "GELEN VERİ AKIŞI: 128 TB/s",
        ]

    def update(self):
        self.timer += 1
        if self.timer > 20: # Log akış hızı
            self.lines.append(f"> {random.choice(self.logs)}")
            if len(self.lines) > 8: # Maksimum satır sayısı
                self.lines.pop(0)
            self.timer = 0

    def draw(self, surface):
        # Arka plan
        s = pygame.Surface((self.rect.w, self.rect.h))
        s.set_alpha(200)
        s.fill((0, 10, 0))
        surface.blit(s, self.rect)
        pygame.draw.rect(surface, (0, 100, 0), self.rect, 1)
        
        y = self.rect.y + 5
        for line in self.lines:
            # Son satır daha parlak
            col = (0, 255, 0) if line == self.lines[-1] else (0, 150, 0)
            txt = self.font.render(line, True, col)
            surface.blit(txt, (self.rect.x + 5, y))
            y += 15

class TerminalButton:
    """Hacker temalı interaktif buton."""
    def __init__(self, x, y, text, cmd):
        self.rect = pygame.Rect(x, y, 400, 40)
        self.text = text
        self.cmd = cmd
        self.font = pygame.font.SysFont("Consolas", 24, bold=True)
        self.hovered = False
        self.blink_timer = 0

    def draw(self, surface, mx, my):
        self.hovered = self.rect.collidepoint(mx, my)
        self.blink_timer += 1
        
        # Renkler
        if self.hovered:
            color = (200, 255, 200) # Çok açık yeşil (Seçili)
            prefix = "> "
            suffix = " <" if (self.blink_timer // 10) % 2 == 0 else "  " # Yanıp sönen imleç
            
            # Arka plana hafif bir bar
            bg_bar = pygame.Surface((self.rect.w, self.rect.h))
            bg_bar.set_alpha(50)
            bg_bar.fill((0, 255, 0))
            surface.blit(bg_bar, self.rect)
        else:
            color = (0, 180, 0) # Normal yeşil
            prefix = "  "
            suffix = ""

        display_text = f"{prefix}{self.text}{suffix}"
        txt_surf = self.font.render(display_text, True, color)
        
        # Yazıyı sola yasla ama dikeyde ortala
        surface.blit(txt_surf, (self.rect.x + 10, self.rect.y + (self.rect.h - txt_surf.get_height())//2))
        
        return self.hovered

class CyberMenu:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((Config.WIDTH, Config.HEIGHT), pygame.DOUBLEBUF)
        pygame.display.set_caption("TERMINAL UPLINK v9.0")
        self.clock = pygame.time.Clock()
        self.sound = SoundSystem()
        self.crt = CRTRenderer(Config.WIDTH, Config.HEIGHT)
        
        # --- THEME ASSETS ---
        self.font_header = pygame.font.SysFont("Consolas", 60, bold=True)
        self.font_sub = pygame.font.SysFont("Consolas", 20)
        
        # 1. Matrix Akışı
        self.streams = [MatrixStream(x, Config.HEIGHT) for x in range(0, Config.WIDTH, 20)]
        
        # 2. Sistem Grafikleri (Sağ Panel)
        self.cpu_graph = SystemGraph(Config.WIDTH - 220, 150, 200, 100, "CPU_THREAD_0")
        self.ram_graph = SystemGraph(Config.WIDTH - 220, 280, 200, 100, "VRAM_ALLOC")
        
        # 3. Log Konsolu (Alt Panel)
        self.console = LogConsole(50, Config.HEIGHT - 150, Config.WIDTH - 100, 130)

        self.cheat_code = [] # Girilen harfleri tutacak

        # 4. Butonlar (Sol Panel)
        start_y = 250
        self.buttons = [
            TerminalButton(50, start_y, "AVATAR_BAGLANTISI", "cam"),
            TerminalButton(50, start_y + 50, "GOREVI_BASLAT", "play"),
            TerminalButton(50, start_y + 100, "LISANS_VERITABANI", "cert"),
            TerminalButton(50, start_y + 150, "GOREVI_IPTAL_ET", "quit")
        ]

    def run(self):
        # Sinematik Giriş (Değiştirmiyoruz, o zaten güzel)
        CinematicBoot(self.screen, self.sound).run()
        self.sound.play_music("music_bg")
        
        running = True
        t_start = time.time()
        
        while running:
            mx, my = pygame.mouse.get_pos()
            current_time = pygame.time.get_ticks()
            
            # 1. Siyah Arka Plan (Temizle)
            self.screen.fill((0, 10, 0)) # Çok koyu yeşil, tam siyah değil
            
            # 2. Matrix Yağmuru (En arkada)
            for s in self.streams:
                s.update(current_time)
                s.draw(self.screen)
                
            # Arka planı biraz karart (UI okunsun diye)
            overlay = pygame.Surface((Config.WIDTH, Config.HEIGHT))
            overlay.set_alpha(100)
            overlay.fill((0, 0, 0))
            self.screen.blit(overlay, (0,0))

            # 3. Başlık Bloğu
            # Yanıp sönen bir cursor efekti ile başlık
            cursor = "_" if (current_time // 500) % 2 == 0 else ""
            title = self.font_header.render("AVATAR_RUNNER" + cursor, True, (0, 255, 0))
            sub = self.font_sub.render("YETKSIZ GIRIS TESPITI // GUVENLI MOD", True, (0, 150, 0))
            
            self.screen.blit(title, (50, 50))
            self.screen.blit(sub, (50, 110))
            
            # Dekoratif Çizgi
            pygame.draw.line(self.screen, (0, 255, 0), (50, 140), (Config.WIDTH - 50, 140), 2)

            # 4. Sağ Panel (Grafikler)
            self.cpu_graph.update()
            self.cpu_graph.draw(self.screen)
            self.ram_graph.update()
            self.ram_graph.draw(self.screen)
            
            # Dekoratif kutu (Grafiklerin etrafına)
            panel_rect = pygame.Rect(Config.WIDTH - 240, 120, 230, 300)
            pygame.draw.rect(self.screen, (0, 100, 0), panel_rect, 1)
            tech_txt = self.font_sub.render("SYS_MONITOR", True, (0, 100, 0))
            self.screen.blit(tech_txt, (Config.WIDTH - 240, 100))

            # 5. Alt Panel (Log Konsolu)
            self.console.update()
            self.console.draw(self.screen)

            # 6. Sol Panel (Butonlar)
            for btn in self.buttons:
                btn.draw(self.screen, mx, my)

            # 7. Son Dokunuşlar (CRT Efekti)
            self.crt.render(self.screen, 0) # Hafif scanline

            pygame.display.flip()
            self.clock.tick(60)
            
            # --- Event Handling ---
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False

                # --- YENİ: KLAVYE DİNLEME (GİZLİ KOD İÇİN) ---
                if e.type == pygame.KEYDOWN:
                    # Basılan harfi listeye ekle
                    if e.unicode.isalpha():
                        self.cheat_code.append(e.unicode.upper())
                        # Sadece son 5 harfi tut
                        if len(self.cheat_code) > 5:
                            self.cheat_code.pop(0)
                        
                        # Kod Kontrolü: GOLGE
                        code_str = "".join(self.cheat_code)
                        if code_str == "GOLGE":
                            self.sound.play_sfx("powerup")
                            # Hikaye Terminali
                            LoreTerminal(self.screen, self.sound).run()
                            # Çıkınca menü müziğini tekrar başlat
                            self.sound.play_music("music_bg")
                            self.cheat_code = []
                            # Menüye döndüğünde ekranın bozulmaması için yeniden boyutlandırma
                            self.screen = pygame.display.set_mode((Config.WIDTH, Config.HEIGHT), pygame.DOUBLEBUF)

                if e.type == pygame.MOUSEBUTTONDOWN:
                    for btn in self.buttons:
                        if btn.rect.collidepoint(mx, my):
                            self.sound.play_sfx("ui")
                            
                            # Tıklama Efekti
                            flash = pygame.Surface((Config.WIDTH, Config.HEIGHT))
                            flash.fill((0, 255, 0))
                            flash.set_alpha(100)
                            self.screen.blit(flash, (0,0))
                            pygame.display.flip()
                            pygame.time.delay(50)
                            
                            if btn.cmd == "quit": running = False
                            elif btn.cmd == "cam":
                                pygame.mouse.set_visible(True); AvatarCam().run(); self.screen = pygame.display.set_mode((Config.WIDTH, Config.HEIGHT), pygame.DOUBLEBUF)
                            elif btn.cmd == "play":
                                pygame.mouse.set_visible(False); GameEngine(self.screen, self.sound).run(); self.sound.play_music("music_bg"); pygame.mouse.set_visible(True)
                            elif btn.cmd == "cert":
                                CertSystem().run(); self.screen = pygame.display.set_mode((Config.WIDTH, Config.HEIGHT), pygame.DOUBLEBUF)

        pygame.quit()
        sys.exit()
if __name__ == "__main__":
    CyberMenu().run()