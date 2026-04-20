import random
import sys
from dataclasses import dataclass, field

import pygame


WIDTH, HEIGHT = 1280, 880
FPS = 60

BG = (239, 244, 248)
PANEL = (255, 255, 255)
PANEL_DARK = (32, 44, 57)
TEXT = (25, 33, 42)
MUTED = (94, 106, 119)
LINE = (211, 220, 230)
BLUE = (46, 111, 242)
GREEN = (30, 142, 62)
RED = (209, 67, 67)
YELLOW = (245, 179, 59)
CYAN = (36, 156, 168)
PURPLE = (132, 83, 190)
ORANGE = (226, 122, 55)


def money(value: int) -> str:
    return f"{value:,}원"


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    candidates = ["malgungothic", "맑은 고딕", "notosanscjkkr", "arialunicode", "arial"]
    for name in candidates:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


@dataclass
class Product:
    name: str
    price: int
    cost: int
    stock: int
    color: tuple[int, int, int]
    icon: str


@dataclass
class DayStats:
    sales: int = 0
    sold: int = 0
    failed: int = 0
    thefts: int = 0
    discounts: int = 0
    bonuses: int = 0
    visitors: int = 0
    customer_counts: dict[str, int] = field(default_factory=lambda: {"일반": 0, "VIP": 0, "진상": 0})


@dataclass
class GameState:
    store_name: str = "무인 편의점"
    day: int = 1
    cash: int = 50_000
    start_cash: int = 50_000
    reputation: int = 0
    ad_score: int = 0
    security: int = 0
    last_stats: DayStats | None = None
    game_over: str | None = None

    products: list[Product] = field(
        default_factory=lambda: [
            Product("삼각김밥", 1200, 700, 8, (83, 139, 74), "▲"),
            Product("라면", 1800, 1000, 7, (218, 83, 64), "≋"),
            Product("음료수", 1500, 900, 10, (40, 140, 210), "●"),
            Product("과자", 1300, 800, 9, (230, 159, 58), "◆"),
            Product("도시락", 4500, 3000, 5, (150, 104, 76), "▣"),
            Product("아이스크림", 2000, 1200, 6, (102, 178, 190), "✦"),
        ]
    )

    def low_stock_names(self) -> list[str]:
        return [p.name for p in self.products if p.stock <= 2]

    def product_by_name(self, name: str) -> Product:
        for product in self.products:
            if product.name == name:
                return product
        raise KeyError(name)


class Button:
    def __init__(self, rect, text, action, color=BLUE, enabled=True):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.action = action
        self.color = color
        self.enabled = enabled

    def draw(self, screen, font, mouse_pos):
        if not self.enabled:
            fill = (178, 187, 197)
        elif self.rect.collidepoint(mouse_pos):
            fill = tuple(max(0, c - 18) for c in self.color)
        else:
            fill = self.color
        pygame.draw.rect(screen, fill, self.rect, border_radius=8)
        label = font.render(self.text, True, (255, 255, 255))
        screen.blit(label, label.get_rect(center=self.rect.center))


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("무인 편의점 운영 시뮬레이터")
        self.window = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        self.screen = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_xl = load_font(30, True)
        self.font_lg = load_font(22, True)
        self.font_md = load_font(18)
        self.font_md_bold = load_font(18, True)
        self.font_sm = load_font(15)
        self.font_xs = load_font(13)
        self.font_icon = load_font(26, True)

        self.state = GameState()
        self.logs: list[str] = [
            "무인 편의점 운영을 시작합니다.",
            "재고, 가격, 홍보, 보안을 조절한 뒤 하루 영업을 시작하세요.",
        ]
        self.buttons: list[Button] = []
        self.price_buttons: list[Button] = []
        self.restock_buttons: list[Button] = []
        self.selected_product = 0
        self.draw_scale = 1.0
        self.draw_offset = (0, 0)

    def log(self, message: str):
        self.logs.append(message)
        self.logs = self.logs[-12:]

    def can_spend(self, amount: int) -> bool:
        if self.state.cash < amount:
            self.log(f"자금 부족: {money(amount)}이 필요합니다.")
            return False
        return True

    def restock(self, index: int, amount: int = 2):
        if self.state.game_over:
            return
        product = self.state.products[index]
        total_cost = product.cost * amount
        if not self.can_spend(total_cost):
            return
        self.state.cash -= total_cost
        product.stock += amount
        self.log(f"{product.name} {amount}개를 채웠습니다. 비용 {money(total_cost)}")

    def change_price(self, index: int, delta: int):
        if self.state.game_over:
            return
        product = self.state.products[index]
        old_price = product.price
        product.price = clamp(product.price + delta, 500, 10_000)
        if product.price != old_price:
            self.log(f"{product.name} 가격: {money(old_price)} -> {money(product.price)}")

    def advertise(self, level: int):
        if self.state.game_over:
            return
        plans = {
            1: ("전단지 홍보", 2_000, 1),
            2: ("동네 광고", 5_000, 3),
            3: ("인터넷 광고", 8_000, 5),
        }
        name, cost, gain = plans[level]
        if not self.can_spend(cost):
            return
        self.state.cash -= cost
        self.state.ad_score += gain
        self.log(f"{name} 완료. 홍보 점수 +{gain}, 비용 {money(cost)}")

    def upgrade_security(self, level: int):
        if self.state.game_over:
            return
        plans = {
            1: ("경고문 부착", 1_000, 1),
            2: ("CCTV 추가", 4_000, 3),
            3: ("출입 센서 강화", 7_000, 5),
        }
        name, cost, gain = plans[level]
        if not self.can_spend(cost):
            return
        self.state.cash -= cost
        self.state.security += gain
        self.log(f"{name} 완료. 보안 점수 +{gain}, 비용 {money(cost)}")

    def simulate_day(self):
        if self.state.game_over:
            return

        stats = DayStats()
        visitor_count = min(18, random.randint(4, 8) + self.state.ad_score)
        stats.visitors = visitor_count
        self.log(f"{self.state.day}일차 영업 시작: 예상 손님 {visitor_count}명")

        for _ in range(visitor_count):
            customer_type = random.choice(["일반", "VIP", "진상"])
            stats.customer_counts[customer_type] += 1

            if customer_type == "일반":
                budget = random.randint(2_000, 9_000)
                purchase_count = random.randint(1, 3)
            elif customer_type == "VIP":
                budget = random.randint(7_000, 18_000)
                purchase_count = random.randint(2, 4)
            else:
                budget = random.randint(1_000, 8_000)
                purchase_count = random.randint(1, 3)

            for _ in range(purchase_count):
                product = random.choice(self.state.products)
                if product.stock <= 0:
                    stats.failed += 1
                    self.state.reputation -= 1
                    continue

                if budget < product.price:
                    stats.failed += 1
                    continue

                if product.price >= product.cost * 2 and random.randint(1, 100) <= 35:
                    stats.failed += 1
                    self.state.reputation -= 1
                    continue

                discount = 0
                discount_roll = random.randint(1, 100)
                if discount_roll <= 12:
                    discount = product.price * 10 // 100
                    stats.discounts += 1
                elif discount_roll == 77:
                    discount = product.price * 50 // 100
                    stats.discounts += 1

                theft_rate = 18 if customer_type == "진상" else 7
                theft_rate = max(2, theft_rate - self.state.security)
                if random.randint(1, 100) <= theft_rate:
                    product.stock -= 1
                    stats.thefts += 1
                    stats.failed += 1
                    self.state.reputation -= 2
                    continue

                final_price = product.price - discount
                product.stock -= 1
                self.state.cash += final_price
                stats.sales += final_price
                stats.sold += 1
                budget -= final_price
                self.state.reputation += 2

                if customer_type == "VIP" and random.randint(1, 100) <= 20:
                    bonus = random.randint(500, 2_000)
                    self.state.cash += bonus
                    stats.sales += bonus
                    stats.bonuses += 1
                    self.state.reputation += 1

                if random.randint(1, 100) == 25:
                    self.state.cash += 1_000
                    stats.sales += 1_000
                    stats.bonuses += 1

            if customer_type == "진상" and random.randint(1, 100) <= 25:
                self.state.reputation -= 1

        electricity = random.randint(3_000, 6_000)
        cleaning = random.randint(2_000, 5_000)
        repair = random.randint(2_000, 7_000) if random.randint(1, 100) <= 20 else 0
        cost_total = electricity + cleaning + repair
        self.state.cash -= cost_total

        self.state.last_stats = stats
        low_stock = self.state.low_stock_names()
        self.log(
            f"마감: 매출 {money(stats.sales)}, 판매 {stats.sold}회, 실패 {stats.failed}회, 도난 {stats.thefts}회"
        )
        self.log(f"운영비 {money(cost_total)} 차감. 전기 {money(electricity)}, 청소 {money(cleaning)}, 수리 {money(repair)}")
        if low_stock:
            self.log("재고 부족: " + ", ".join(low_stock))

        self.state.ad_score = max(0, self.state.ad_score - 1)
        self.state.security = max(0, self.state.security - 1)
        self.state.day += 1

        if self.state.cash < 10_000:
            self.state.game_over = f"파산 엔딩: 보유 자금이 {money(self.state.cash)}까지 떨어졌습니다."
            self.log(self.state.game_over)
        elif self.state.cash >= 120_000:
            self.state.game_over = f"대성공 엔딩: 보유 자금 {money(self.state.cash)}을 달성했습니다."
            self.log(self.state.game_over)

    def restart(self):
        self.state = GameState()
        self.logs = [
            "새 게임을 시작했습니다.",
            "재고, 가격, 홍보, 보안을 조절한 뒤 하루 영업을 시작하세요.",
        ]

    def draw_text(self, text, x, y, font, color=TEXT):
        surface = font.render(text, True, color)
        self.screen.blit(surface, (x, y))
        return surface.get_rect(topleft=(x, y))

    def draw_text_in_rect(self, text, rect, font, color=TEXT, align="left"):
        surface = font.render(text, True, color)
        target = surface.get_rect()
        if align == "center":
            target.center = rect.center
        else:
            target.midleft = (rect.x, rect.centery)
        self.screen.blit(surface, target)
        return target

    def draw_wrapped_text(self, text, x, y, font, color, max_width, line_height):
        words = text.split(" ")
        line = ""
        rows = []
        for word in words:
            candidate = word if line == "" else f"{line} {word}"
            if font.size(candidate)[0] <= max_width:
                line = candidate
            else:
                if line:
                    rows.append(line)
                line = word
        if line:
            rows.append(line)

        for row in rows:
            self.draw_text(row, x, y, font, color)
            y += line_height
        return y

    def fit_font(self, text, base_size, max_width, bold=False, min_size=11):
        size = base_size
        font = load_font(size, bold)
        while size > min_size and font.size(text)[0] > max_width:
            size -= 1
            font = load_font(size, bold)
        return font

    def draw_card(self, rect, title=None):
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, LINE, rect, 1, border_radius=8)
        if title:
            self.draw_text(title, rect.x + 18, rect.y + 14, self.font_lg)
        return pygame.Rect(rect.x + 18, rect.y + 54, rect.width - 36, rect.height - 72)

    def draw_header(self):
        rect = pygame.Rect(0, 0, WIDTH, 84)
        pygame.draw.rect(self.screen, PANEL_DARK, rect)
        self.draw_text("무인 편의점 운영 시뮬레이터", 28, 18, self.font_xl, (255, 255, 255))
        self.draw_text(f"{self.state.store_name} · {self.state.day}일차", 31, 52, self.font_sm, (205, 214, 224))

        metrics = [
            ("자금", money(self.state.cash), GREEN if self.state.cash >= 20_000 else RED),
            ("평판", str(self.state.reputation), CYAN),
            ("홍보", str(self.state.ad_score), YELLOW),
            ("보안", str(self.state.security), PURPLE),
        ]
        x = 682
        for label, value, color in metrics:
            metric_rect = pygame.Rect(x, 14, 136, 56)
            pygame.draw.rect(self.screen, (46, 60, 75), metric_rect, border_radius=8)
            self.draw_text(label, metric_rect.x + 12, metric_rect.y + 8, self.font_sm, (192, 203, 214))
            value_font = self.fit_font(value, 18, metric_rect.width - 24, True)
            self.draw_text_in_rect(value, pygame.Rect(metric_rect.x + 12, metric_rect.y + 29, metric_rect.width - 24, 20), value_font, color)
            x += 144

    def draw_products(self):
        rect = pygame.Rect(24, 108, 610, 462)
        self.draw_card(rect, "상품 관리")
        self.restock_buttons.clear()
        self.price_buttons.clear()

        y = 160
        for index, product in enumerate(self.state.products):
            row = pygame.Rect(46, y, 564, 58)
            fill = (248, 251, 253) if index % 2 == 0 else (242, 247, 250)
            if product.stock <= 2:
                fill = (255, 242, 232)
            pygame.draw.rect(self.screen, fill, row, border_radius=8)

            icon_rect = pygame.Rect(row.x + 12, row.y + 10, 38, 38)
            pygame.draw.rect(self.screen, product.color, icon_rect, border_radius=7)
            icon = self.font_icon.render(product.icon, True, (255, 255, 255))
            self.screen.blit(icon, icon.get_rect(center=icon_rect.center))

            self.draw_text(product.name, row.x + 64, row.y + 10, self.font_md_bold)
            self.draw_text(f"가격 {money(product.price)} · 원가 {money(product.cost)}", row.x + 64, row.y + 34, self.font_sm, MUTED)
            stock_color = RED if product.stock <= 2 else TEXT
            self.draw_text(f"재고 {product.stock}개", row.x + 318, row.y + 19, self.font_md_bold, stock_color)

            minus = Button((row.x + 410, row.y + 12, 46, 34), "-100", lambda i=index: self.change_price(i, -100), ORANGE)
            plus = Button((row.x + 462, row.y + 12, 46, 34), "+100", lambda i=index: self.change_price(i, 100), BLUE)
            restock = Button((row.x + 514, row.y + 12, 42, 34), "+2", lambda i=index: self.restock(i, 2), GREEN)
            self.price_buttons.extend([minus, plus])
            self.restock_buttons.append(restock)
            y += 66

        mouse = pygame.mouse.get_pos()
        for button in self.price_buttons + self.restock_buttons:
            button.draw(self.screen, self.font_sm, mouse)

    def draw_actions(self):
        rect = pygame.Rect(24, 592, 610, 264)
        content = self.draw_card(rect, "운영 행동")
        self.buttons.clear()

        x = content.x + 6
        y = content.y + 4
        button_w = 124
        button_h = 38
        button_gap = 12
        row_gap = 18
        label_gap = 12
        group_gap = 22
        start_x = x + 420
        action_h = button_h * 2 + row_gap + group_gap + 20

        self.draw_text("홍보 비용", x, y, self.font_xs, MUTED)
        y += 20
        self.draw_text("2,000 / 5,000 / 8,000원", x, y, self.font_xs, MUTED)
        y += label_gap + 16

        actions = [
            Button((x, y, button_w, button_h), "전단지", lambda: self.advertise(1), CYAN),
            Button((x + button_w + button_gap, y, button_w, button_h), "동네 광고", lambda: self.advertise(2), CYAN),
            Button((x + (button_w + button_gap) * 2, y, button_w, button_h), "인터넷 광고", lambda: self.advertise(3), CYAN),
            Button((start_x, y, 136, action_h), "영업 시작", self.simulate_day, GREEN),
        ]

        y += button_h + group_gap
        pygame.draw.line(self.screen, LINE, (x, y - 8), (start_x - 24, y - 8), 1)
        self.draw_text("보안 비용", x, y, self.font_xs, MUTED)
        y += 20
        self.draw_text("1,000 / 4,000 / 7,000원", x, y, self.font_xs, MUTED)
        y += label_gap + 16

        actions.extend(
            [
                Button((x, y, button_w, button_h), "경고문", lambda: self.upgrade_security(1), PURPLE),
                Button((x + button_w + button_gap, y, button_w, button_h), "CCTV", lambda: self.upgrade_security(2), PURPLE),
                Button((x + (button_w + button_gap) * 2, y, button_w, button_h), "센서 강화", lambda: self.upgrade_security(3), PURPLE),
            ]
        )
        if self.state.game_over:
            actions.append(Button((start_x, rect.bottom - 30, 136, 22), "새 게임", self.restart, RED))
        self.buttons.extend(actions)

        mouse = pygame.mouse.get_pos()
        for button in self.buttons:
            button.draw(self.screen, self.font_xs, mouse)

    def draw_store_scene(self):
        rect = pygame.Rect(660, 108, 596, 340)
        content = self.draw_card(rect, "매장 화면")
        summary_top = content.y
        floor = pygame.Rect(content.x + 10, summary_top + 76, content.width - 20, 180)
        pygame.draw.rect(self.screen, (225, 233, 239), floor, border_radius=8)
        pygame.draw.line(self.screen, (196, 207, 218), (floor.x, floor.y + 96), (floor.right, floor.y + 96), 2)

        shelf_x = floor.x + 30
        for product in self.state.products:
            shelf_rect = pygame.Rect(shelf_x, floor.y + 26, 56, 124)
            pygame.draw.rect(self.screen, (67, 81, 95), shelf_rect, border_radius=6)
            for n in range(min(product.stock, 5)):
                item_rect = pygame.Rect(shelf_rect.x + 10, shelf_rect.y + 10 + n * 21, 36, 15)
                pygame.draw.rect(self.screen, product.color, item_rect, border_radius=4)
            self.draw_text(product.name[:3], shelf_rect.x + 3, floor.y + 154, self.font_xs, MUTED)
            shelf_x += 82

        door = pygame.Rect(floor.x + 8, floor.y + 26, 24, 104)
        pygame.draw.rect(self.screen, (74, 151, 190), door, border_radius=3)
        pygame.draw.circle(self.screen, (255, 255, 255), (door.x + 18, door.y + 52), 3)

        if self.state.last_stats:
            stats = self.state.last_stats
            summary = [
                f"최근 손님 {stats.visitors}명",
                f"일반 {stats.customer_counts['일반']} · VIP {stats.customer_counts['VIP']} · 진상 {stats.customer_counts['진상']}",
                f"판매 {stats.sold}회 · 도난 {stats.thefts}회 · 할인 {stats.discounts}회",
            ]
        else:
            summary = ["아직 영업 전입니다.", "버튼으로 재고와 가격을 조정하세요.", "영업 시작을 누르면 하루가 진행됩니다."]
        y = summary_top
        for line in summary:
            y = self.draw_wrapped_text(line, content.x + 10, y, self.font_xs, MUTED, content.width - 20, 18)

    def draw_log(self):
        rect = pygame.Rect(660, 468, 596, 388)
        self.draw_card(rect, "운영 로그")
        y = 518
        bottom = rect.bottom - 18
        for message in self.logs[-9:]:
            color = RED if "부족" in message or "파산" in message or "도난" in message else TEXT
            if "대성공" in message:
                color = GREEN
            y = self.draw_wrapped_text("· " + message, 686, y, self.font_sm, color, 536, 21)
            y += 4
            if y > bottom:
                break

        if self.state.game_over:
            overlay = pygame.Rect(700, 704, 512, 62)
            pygame.draw.rect(self.screen, (255, 250, 232), overlay, border_radius=8)
            pygame.draw.rect(self.screen, YELLOW, overlay, 2, border_radius=8)
            self.draw_text(self.state.game_over, overlay.x + 16, overlay.y + 20, self.font_md_bold, TEXT)

    def draw(self):
        self.screen.fill(BG)
        self.draw_header()
        self.draw_products()
        self.draw_actions()
        self.draw_store_scene()
        self.draw_log()
        window_w, window_h = self.window.get_size()
        scale = min(window_w / WIDTH, window_h / HEIGHT)
        scaled_w = max(1, int(WIDTH * scale))
        scaled_h = max(1, int(HEIGHT * scale))
        offset_x = (window_w - scaled_w) // 2
        offset_y = (window_h - scaled_h) // 2
        self.draw_scale = scale
        self.draw_offset = (offset_x, offset_y)

        self.window.fill(BG)
        scaled = pygame.transform.smoothscale(self.screen, (scaled_w, scaled_h))
        self.window.blit(scaled, (offset_x, offset_y))
        pygame.display.flip()

    def handle_click(self, pos):
        offset_x, offset_y = self.draw_offset
        if self.draw_scale <= 0:
            return
        pos = ((pos[0] - offset_x) / self.draw_scale, (pos[1] - offset_y) / self.draw_scale)
        for button in self.price_buttons + self.restock_buttons + self.buttons:
            if button.enabled and button.rect.collidepoint(pos):
                button.action()
                return

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self.simulate_day()
                    elif event.key == pygame.K_r:
                        self.restart()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)

            self.draw()
            self.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    try:
        Game().run()
    except pygame.error as exc:
        print("pygame 실행 중 오류가 발생했습니다.")
        print(exc)
        sys.exit(1)
