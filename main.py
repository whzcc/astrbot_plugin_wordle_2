import os
import random
import json
import base64
from io import BytesIO

from PIL import Image as ImageW
from PIL import ImageDraw, ImageFont

from astrbot.api.all import *  # noqa: F403
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star, register

TMPL = '''
<div style="width: 100%; line-height: 0; padding-top: 20px;">
<img src="{{ footer_image }}"
     style="display: block;
            width: 100%;
            height: auto;
            object-fit: contain;"
     alt="自适应插图">
</div>
'''

try:
    os.system("pip install pyspellchecker")
    logger.log("Wordle已尝试安装pyspellchecker库")
except:
    logger.warning("Wordle未自动安装pyspellchecker库")
    logger.warning("这可能导致拼写检查的失败，请手动在AstrBot目录中requirements.txt添加一行“pyspellchecker”，如已安装请忽略")

from spellchecker import SpellChecker

class WordleGame:
    def __init__(self, answer: str):
        self.answer = answer.upper()
        self.length = len(answer)
        self.max_attempts = self.length + 1
        self.guesses: list[str] = []
        self.feedbacks: list[list[int]] = []
        self.history_letters: list[str] = []
        self.history_words: list[str] = []

        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))  # 获取当前文件所在目录
        self.font_file = os.path.join(self.plugin_dir, "MinecraftAE.ttf")   # 这里可以修改字体为自定义字体

        self._font = ImageFont.truetype(self.font_file, 40)  #设定字体、字号、字重

    async def gen_image(self) -> bytes:
        CELL_COLORS = {
            2: (106, 170, 100),
            1: (201, 180, 88),
            0: (120, 124, 126),
            -1: (211, 214, 218),
        }
        BACKGROUND_COLOR = (255, 255, 255)
        TEXT_COLOR = (255, 255, 255)

        CELL_SIZE = 60
        CELL_MARGIN = 5
        GRID_MARGIN = 5

        cell_stride = CELL_SIZE + CELL_MARGIN
        width = GRID_MARGIN * 2 + cell_stride * self.length - CELL_MARGIN
        height = GRID_MARGIN * 2 + cell_stride * self.max_attempts - CELL_MARGIN

        image = ImageW.new("RGB", (width, height), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)

        for row in range(self.max_attempts):
            y = GRID_MARGIN + row * cell_stride

            for col in range(self.length):
                x = GRID_MARGIN + col * cell_stride

                if row < len(self.guesses) and col < len(self.guesses[row]):
                    letter = self.guesses[row][col].upper()
                    feedback_value = self.feedbacks[row][col]
                    cell_color = CELL_COLORS[feedback_value]
                else:
                    letter = ""
                    cell_color = CELL_COLORS[-1]

                draw.rectangle(
                    [x, y, x + CELL_SIZE, y + CELL_SIZE], fill=cell_color, outline=None
                )

                if letter:
                    text_bbox = draw.textbbox((0, 0), letter, font=self._font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]

                    letter_x = x + (CELL_SIZE - text_width) // 2 + 2.5
                    letter_y = y + (CELL_SIZE - text_height) // 2 + 1

                    draw.text((letter_x, letter_y), letter, fill=TEXT_COLOR, font=self._font)

        with BytesIO() as output:
            image.save(output, format="PNG")
            return output.getvalue()

    async def gen_image_hint(self,word) -> bytes:    # 与gen_image()相似，但需要传参
        CELL_COLORS = {
            2: (106, 170, 100),
            1: (201, 180, 88),
            0: (120, 124, 126),
            -1: (211, 214, 218),
        }
        BACKGROUND_COLOR = (255, 255, 255)
        TEXT_COLOR = (255, 255, 255)

        CELL_SIZE = 60
        CELL_MARGIN = 5
        GRID_MARGIN = 5

        cell_stride = CELL_SIZE + CELL_MARGIN
        width = GRID_MARGIN * 2 + cell_stride * self.length - CELL_MARGIN
        height = GRID_MARGIN * 2 + cell_stride * 1 - CELL_MARGIN

        image = ImageW.new("RGB", (width, height), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)

        for row in range(1):
            y = GRID_MARGIN + row * cell_stride

            hint_word = [word]

            for col in range(self.length):
                x = GRID_MARGIN + col * cell_stride

                logger.fatal(hint_word)

                if word[col] == " ":
                    cell_color = CELL_COLORS[-1]
                else:
                    cell_color = CELL_COLORS[2]
                letter = word[col]

                draw.rectangle(
                    [x, y, x + CELL_SIZE, y + CELL_SIZE], fill=cell_color, outline=None
                )

                text_bbox = draw.textbbox((0, 0), letter, font=self._font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                letter_x = x + (CELL_SIZE - text_width) // 2 + 2.5
                letter_y = y + (CELL_SIZE - text_height) // 2 + 1

                draw.text((letter_x, letter_y), letter, fill=TEXT_COLOR, font=self._font)

        with BytesIO() as output:
            image.save(output, format="PNG")
            return output.getvalue()

    # 未完工
    async def is_guessed(self, word: str) -> bool:
        if word in self.history_words:
            logger.info(f"is_guessed()函数:历史猜测的单词重复，未更新历史单词列表。")
            return True
        else:
            self.history_words.append(word)
            logger.info(f"is_guessed()函数:历史猜测的单词更新为{self.history_words}。")
            return False

    async def guess(self, word: str) -> bytes:
        word = word.upper()
        self.guesses.append(word)
        for i in range(len(word)):
            self.history_letters.append(word[i])
        
        logger.info(f"guess()函数:历史猜测的字母表更新为{self.history_letters}。")

        feedback = [0] * self.length
        answer_char_counts: dict[str, int] = {}
        
        for i in range(self.length):
            if word[i] == self.answer[i]:
                feedback[i] = 2
            else:
                answer_char_counts[self.answer[i]] = answer_char_counts.get(self.answer[i], 0) + 1
        
        for i in range(self.length):
            if feedback[i] != 2:
                char = word[i]
                if char in answer_char_counts and answer_char_counts[char] > 0:
                    feedback[i] = 1
                    answer_char_counts[char] -= 1
        
        self.feedbacks.append(feedback)
        result = await self.gen_image()

        return result
    
    async def hint(self) -> bytes:   # 原理和guess()相同，但本函数无需传参
        for i in range(len(self.answer)):
            if self.answer[i] in self.history_letters:
                guessed_correct_letters = True
            else:
                guessed_correct_letters = False
        if not guessed_correct_letters:
            logger.warning("用户还未猜出任何一个正确的字母。")
            return False
        else:
            logger.critical("hint()被调用")
            # 组建“提示”的单词，未猜出的字母用空格代替
            hint_word = ""
            for i in range(len(self.answer)):
                if self.answer[i] in self.history_letters:
                    hint_word = hint_word + self.answer[i]
                else:
                    hint_word = hint_word + " "
            hint_word = hint_word.upper()
            logger.fatal(hint_word)

            # 废弃，我不需要（
            # feedback = [0] * self.length
            # answer_char_counts: dict[str, int] = {}
            
            # for i in range(self.length):
            #     if word[i] == self.answer[i]:
            #         feedback[i] = 2
            #     else:
            #         answer_char_counts[self.answer[i]] = answer_char_counts.get(self.answer[i], 0) + 1
            
            # for i in range(self.length):
            #     if feedback[i] != 2:
            #         char = word[i]
            #         if char in answer_char_counts and answer_char_counts[char] > 0:
            #             feedback[i] = 1
            #             answer_char_counts[char] -= 1
            
            # self.feedbacks.append(feedback)
            result = await self.gen_image_hint(hint_word)

            return result
    
    @property
    def is_game_over(self):
        if not self.guesses:
            return False
        return len(self.guesses) >= self.max_attempts

    @property
    def is_won(self):
        return self.guesses and self.guesses[-1].upper() == self.answer


@register(
    "astrbot_plugin_wordle",
    "Raven95676",
    "Astrbot wordle游戏，支持指定位数",
    "2.0.0",
    "https://github.com/Raven95676/astrbot_plugin_wordle",
)
class PluginWordle(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.game_sessions: dict[str, WordleGame] = {}

    @staticmethod
    async def get_answer(length):
        try:
            wordlist_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "wordlist"
            )

            if not os.path.exists(wordlist_path):
                logger.error("词表文件不存在")
                return None

            # 获取单词文件
            word_file_list = os.listdir(wordlist_path)
            global word_dict
            word_dict = {}
            # 遍历单词表，并用字典接收内容
            for word_file in word_file_list:
                with open(os.path.join(wordlist_path,word_file),"r",encoding="utf-8") as f:
                    word_dict.update(json.load(f)) 
                    # 只保留长度为length的单词
                    for word in list(word_dict.keys()):
                        if len(word) != length:
                            del word_dict[word]

            # 随机选一个单词
            word = random.choice(list(word_dict.keys()))
            global explanation
            explanation = word_dict[word]["中释"]

            logger.info(f"选择了{word}单词，长度{length}，释义为{explanation}")

            return word.upper()
        
        except Exception as e:
            logger.error(f"加载词表失败: {e!s}")
            return None

    @event_message_type(EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        msg = event.get_message_str()
        try:
            msg = msg.lower()
            logger.info(f"用户输入（已转为小写）：{msg}")
        except:
            logger.info(f"用户输入（未转为小写）：{msg}")
        
        if "猜单词结束" in msg:
            """中止Wordle游戏"""
            session_id = event.unified_msg_origin
            if session_id in self.game_sessions:
                del self.game_sessions[session_id]
                yield event.plain_result("猜单词已结束。")
            else:
                yield event.plain_result("游戏还没开始，输入“/猜单词”来开始游戏吧！")

        if "猜单词提示" in msg:
            session_id = event.unified_msg_origin
            if session_id not in self.game_sessions:
                yield event.plain_result("游戏还没开始，输入“/猜单词”来开始游戏吧！")
                return
            game = self.game_sessions[session_id]

            image_result_hint = await game.hint()

            if not image_result_hint == False:  # 当用户猜出来过正确的字母时，给出图片形式的提示
                
                # 将二进制数据编码为Base64字符串
                base64_encoded_data = base64.b64encode(image_result_hint)
                # 创建一个可以直接在HTML中使用的Data URL：
                picture_url = 'data:image/png;base64,' + base64_encoded_data.decode('utf-8')
                url = await self.html_render(TMPL,
        {"footer_image": picture_url})
                
                chain = [
                    Image.fromURL(url),
                    Plain("这是你已经猜出的字母。")
                ]
                yield event.chain_result(chain)
            else:   # 当用户一个字母都没有猜出来过时，给出文本形式的提示
                i = random.randint(0,len(game.answer)-1)
                hint = f"提示：第{i+1}个字母是 {game.answer[i]}。"
                yield event.plain_result(hint)
    
        if "/猜单词" in msg and not "提示" in msg and not "结束" in msg:
            length = msg.strip("/猜单词 ")
            logger.info(length)
            if length == "":
                length = 5
                user_length_ok = True
            else:
                try:
                    length = int(length)
                    user_length_ok = True
                except:
                    length = 5
                    user_length_ok = False
            """开始Wordle游戏"""
            answer = await self.get_answer(length)
            session_id = event.unified_msg_origin
            if session_id in self.game_sessions:
                del self.game_sessions[session_id]
            if not answer:
                random_text = random.choice([
                    f"{length}个字母长度的单词，我找不到啊……",
                    f"{length}个字母的单词好像有点稀有哦，换一个吧！",
                    "没找到这么长的单词，换一个吧！"
                ])
                yield event.plain_result(random_text)
            else:
                game = WordleGame(answer)
                self.game_sessions[session_id] = game
                logger.debug(f"答案是：{answer}")
                if user_length_ok:
                    random_text = random.choice([
                            f"游戏开始！请输入长度为{length}的单词。",
                            f"游戏开始了！请输入长度为{length}的单词。",
                            f"游戏开始了！请输入长度为{length}的单词。"
                        ])
                elif not user_length_ok:
                    random_text = random.choice([
                            f"不清楚你想猜多长的单词，那就{length}个字母的吧！",
                            f"你想猜多长的单词？长度{length}如何？游戏开始！",
                            f"不明白你的意思，但是，游戏开始！请输入长度为{length}的单词。",
                            f"单词长度{length}如何？游戏开始，请输入！",
                        ])
                yield event.plain_result(random_text)
            pass

        session_id = event.unified_msg_origin
        if session_id in self.game_sessions and event.is_at_or_wake_command:
            game = self.game_sessions[session_id]

            if "猜单词" in msg or "猜单词结束" in msg or "猜单词提示" in msg:
                return
            
            else:
                
                length = game.length
                spellcheck = SpellChecker()

                if not msg.isalpha():
                    random_text = random.choice([
                    "你要输入英语才行啊😉！",
                    "语言不正确哦，要输入英语单词。",
                    "我以后就可以用其他语言猜单词了，不过现在还是用英语吧！",
                    "Try in English💬!", 
                    "需要英文单词～🔡",  
                    "Alphabet Only!🔤", 
                    "外星挑战：地球英文输入🛸。", 
                    "符号错误🔣，需要纯字母。", 
                    "❗Error: Expected ENGLISH :("
                ])
                    random_text = random_text + "\n输入“猜单词结束”就可以结束游戏，输入“猜单词提示”可以获得提示。"
                    yield event.plain_result(random_text)
                    return
                
                elif len(msg) != length:
                    random_text = random.choice([
                    f"你要输入{length}字母的英语单词才行啊😉！",
                    f"不太对哦，要输入{length}个字母的英语单词🔡。",
                    f"❗Error: Expected ENGLISH, and WORDLENGTH being {length} :(",
                    f"需要{length}个字母长的英语单词～🔡", 
                    f"输入有问题！请输入{length}个字母长的英语单词。",
                    f"回答错误❌！应该是有{length}个字母的英语单词。",
                    f"戳啦🌀！请输入{length}个字母的英语单词。"

                ])
                    random_text = random_text + "\n输入“猜单词结束”就可以结束游戏，输入“猜单词提示”可以获得提示。"
                    yield event.plain_result(random_text)
                    return   
                    
                elif not(
                    msg in list(word_dict.keys())
                    or spellcheck.known((msg,))
                    ):
                    random_text = random.choice([
                    "拼写错误😉！",
                    "拼错了哦，试试重新拼一下单词吧！",
                    "单词拼写不正确！",
                    "拼写有误🌀，再试一次吧！",
                    "（你确定这个单词存在吗😲？）",
                    "拼写错误，请检查拼写！",
                    ])
                    random_text = random_text + "\n输入“猜单词结束”就可以结束游戏，输入“猜单词提示”可以获得提示。"
                    yield event.plain_result(random_text)
                    return
                
            image_result = await game.guess(msg)

            if game.is_won:
                sender_info = event.get_sender_name() if event.get_sender_name() else event.get_sender_id()
                random_text = random.choice([
                    "恭喜你猜对了😉！",
                    "Cool🎉！",
                    "答案正确✅！"
                    "太棒了🎉！", 
                    "猜中啦🎯！",  
                    "冠军🥇！", 
                    "天才🌟！", 
                    "胜利🏆！", 
                    "满分💯！", 
                    "王者👑！", 
                    "绝了🤩！"
                ])
                if random.randint(1,22) == 1:
                    random_text = "🔠🥳语言神，启动🔠🥳！"
                game_status = f"{random_text}“{game.answer}”的意思是“{explanation}”。"
                del self.game_sessions[session_id]
            elif game.is_game_over:
                game_status = f"没有人猜出答案啊Σ(°△°|||)︴\n正确答案是“{game.answer}”，意思是“{explanation}”。"
                del self.game_sessions[session_id]
            else:
                game_status = f"已猜测 {len(game.guesses)}/{game.max_attempts} 次。"
                logger.info(f"已猜测 {len(game.guesses)}/{game.max_attempts} 次。")


            # 将二进制数据编码为Base64字符串
            base64_encoded_data = base64.b64encode(image_result)

            # 创建一个可以直接在HTML中使用的Data URL：
            picture_url = 'data:image/png;base64,' + base64_encoded_data.decode('utf-8')

            url = await self.html_render(TMPL,
    {"footer_image": picture_url})
            print(url)
            
            chain = [
                # Image.fromBytes(image_result),  # noqa: F405
                Image.fromURL(url),
                Plain(game_status),  # noqa: F405
            ]

            yield event.chain_result(chain)

            # yield event.image_result(url)
