"""
Модуль безопасности TgSpyBot
Шифрование session файлов и конфиденциальных данных
"""
import os
import hashlib
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from loguru import logger

from app.config.settings import settings


class SecurityManager:
    """Менеджер безопасности для шифрования данных"""
    
    def __init__(self):
        self._fernet: Optional[Fernet] = None
        self._initialized = False
    
    def _initialize_encryption(self) -> bool:
        """Инициализация шифрования"""
        try:
            if self._initialized:
                return True
            
            # Получаем ключ шифрования из настроек
            encryption_key = settings.security.encryption_key
            
            if len(encryption_key) < 32:
                # Генерируем ключ на основе пароля
                key = self._derive_key_from_password(encryption_key)
            else:
                # Используем ключ напрямую
                key = encryption_key[:32].encode()
            
            # Создаём Fernet ключ
            fernet_key = base64.urlsafe_b64encode(key)
            self._fernet = Fernet(fernet_key)
            self._initialized = True
            
            logger.info("✅ Система шифрования инициализирована")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации шифрования: {e}")
            return False
    
    def _derive_key_from_password(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """Генерация ключа шифрования из пароля"""
        if salt is None:
            # Используем фиксированный salt на основе пароля для воспроизводимости
            salt = hashlib.sha256(password.encode()).digest()[:16]
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        return kdf.derive(password.encode())
    
    def encrypt_data(self, data: Union[str, bytes]) -> Optional[bytes]:
        """Шифрование данных"""
        try:
            if not self._initialize_encryption():
                return None
            
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            encrypted = self._fernet.encrypt(data)
            logger.debug("Данные зашифрованы")
            return encrypted
            
        except Exception as e:
            logger.error(f"Ошибка шифрования: {e}")
            return None
    
    def decrypt_data(self, encrypted_data: bytes) -> Optional[str]:
        """Расшифровка данных"""
        try:
            if not self._initialize_encryption():
                return None
            
            decrypted = self._fernet.decrypt(encrypted_data)
            result = decrypted.decode('utf-8')
            logger.debug("Данные расшифрованы")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка расшифровки: {e}")
            return None
    
    def encrypt_file(self, file_path: str, output_path: Optional[str] = None) -> bool:
        """Шифрование файла"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"Файл не найден: {file_path}")
                return False
            
            # Читаем файл
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Шифруем
            encrypted_data = self.encrypt_data(file_data)
            if encrypted_data is None:
                return False
            
            # Определяем путь для сохранения
            if output_path is None:
                output_path = file_path + '.encrypted'
            
            # Сохраняем зашифрованный файл
            with open(output_path, 'wb') as f:
                f.write(encrypted_data)
            
            logger.info(f"Файл зашифрован: {file_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка шифрования файла {file_path}: {e}")
            return False
    
    def decrypt_file(self, encrypted_file_path: str, output_path: Optional[str] = None) -> bool:
        """Расшифровка файла"""
        try:
            if not os.path.exists(encrypted_file_path):
                logger.error(f"Зашифрованный файл не найден: {encrypted_file_path}")
                return False
            
            # Читаем зашифрованный файл
            with open(encrypted_file_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Расшифровываем
            decrypted_data = self.decrypt_data(encrypted_data)
            if decrypted_data is None:
                return False
            
            # Определяем путь для сохранения
            if output_path is None:
                output_path = encrypted_file_path.replace('.encrypted', '')
            
            # Сохраняем расшифрованный файл
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(decrypted_data)
            
            logger.info(f"Файл расшифрован: {encrypted_file_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка расшифровки файла {encrypted_file_path}: {e}")
            return False
    
    def secure_delete_file(self, file_path: str) -> bool:
        """Безопасное удаление файла с перезаписью"""
        try:
            if not os.path.exists(file_path):
                return True
            
            # Получаем размер файла
            file_size = os.path.getsize(file_path)
            
            # Перезаписываем файл случайными данными несколько раз
            with open(file_path, 'r+b') as f:
                for _ in range(3):
                    f.seek(0)
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())
            
            # Удаляем файл
            os.remove(file_path)
            logger.info(f"Файл безопасно удален: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка безопасного удаления файла {file_path}: {e}")
            return False
    
    def hash_password(self, password: str, salt: Optional[str] = None) -> tuple:
        """Хеширование пароля с солью"""
        if salt is None:
            salt = os.urandom(32).hex()
        
        # Создаём хеш пароля
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        
        return password_hash.hex(), salt
    
    def verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """Проверка пароля"""
        try:
            # Хешируем введенный пароль с той же солью
            new_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            )
            
            return new_hash.hex() == password_hash
            
        except Exception as e:
            logger.error(f"Ошибка проверки пароля: {e}")
            return False
    
    @staticmethod
    def generate_encryption_key() -> str:
        """Генерация случайного ключа шифрования"""
        return Fernet.generate_key().decode()
    
    def mask_sensitive_data(self, data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
        """Маскировка конфиденциальных данных для логов"""
        if len(data) <= visible_chars * 2:
            return mask_char * len(data)
        
        start = data[:visible_chars]
        end = data[-visible_chars:]
        middle = mask_char * (len(data) - visible_chars * 2)
        
        return f"{start}{middle}{end}"


class SessionFileManager:
    """Менеджер session файлов Telegram с шифрованием"""
    
    def __init__(self, security_manager: SecurityManager):
        self.security = security_manager
        self.session_path = settings.telegram.session_file
        self.encrypted_session_path = self.session_path + '.enc'
    
    def save_encrypted_session(self) -> bool:
        """Сохранение зашифрованного session файла"""
        try:
            if not os.path.exists(self.session_path + '.session'):
                logger.warning("Session файл не найден для шифрования")
                return False
            
            # Шифруем session файл
            success = self.security.encrypt_file(
                self.session_path + '.session',
                self.encrypted_session_path
            )
            
            if success and settings.security.session_encryption:
                # Безопасно удаляем оригинальный session файл
                self.security.secure_delete_file(self.session_path + '.session')
                logger.info("Session файл зашифрован и оригинал удален")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка сохранения зашифрованного session: {e}")
            return False
    
    def load_encrypted_session(self) -> bool:
        """Загрузка зашифрованного session файла"""
        try:
            if not os.path.exists(self.encrypted_session_path):
                logger.info("Зашифрованный session файл не найден")
                return False
            
            # Расшифровываем session файл
            success = self.security.decrypt_file(
                self.encrypted_session_path,
                self.session_path + '.session'
            )
            
            if success:
                logger.info("Session файл расшифрован")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка загрузки зашифрованного session: {e}")
            return False
    
    def cleanup_session_files(self) -> bool:
        """Очистка session файлов"""
        try:
            files_to_clean = [
                self.session_path + '.session',
                self.session_path + '.session-journal',
                self.encrypted_session_path
            ]
            
            for file_path in files_to_clean:
                if os.path.exists(file_path):
                    self.security.secure_delete_file(file_path)
            
            logger.info("Session файлы очищены")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка очистки session файлов: {e}")
            return False


# Глобальные экземпляры
security_manager = SecurityManager()
session_manager = SessionFileManager(security_manager) 