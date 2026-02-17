import React, { useState, useEffect } from 'react';
import './AuthForm.css';
import { AuthenticationServiceService } from '../../../../api/services/AuthenticationServiceService.ts';
import Logo from './Logo.tsx';
import LoadingPage from './LoadingPage.tsx';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, User } from 'lucide-react';

const ERROR_MESSAGES: Record<string, string> = {
  "A-1000": "Внутренняя ошибка сервера. Попробуйте позже.",
  "A-S1001": "Неверные данные для регистрации.",
  "A-L1001": "Неверный логин или пароль.",
  "A-L1002": "Аккаунт заблокирован. Обратитесь в поддержку.",
  "A-L1003": "Слишком много попыток входа. Подождите немного.",

  "A-AT1001": "Сессия истекла. Войдите заново.",
  "A-AT1002": "Ошибка безопасности (неверная подпись токена).",

  "A-RT1001": "Сессия обновления истекла. Пожалуйста, авторизуйтесь снова.",
  "A-RT1002": "Некорректный запрос на обновление сессии.",

  "A-R1001": "У вас недостаточно прав для этого действия.",
  "A-R1002": "Доступ к ресурсу запрещен.",
  "A-R1003": "Ваша роль не позволяет выполнить это действие.",
};

const AuthForm: React.FC = () => {
    const [isSignUp, setIsSignUp] = useState<boolean>(false);
    const [isSignIn, setIsSignIn] = useState<boolean>(true);
    const [passwordError, setPasswordError] = useState<string | null>(null);
    const [emailError, setEmailError] = useState<string | null>(null);
    const [serverError, setServerError] = useState<string | null>(null);
    const [email, setEmail] = useState<string>("");
    const [password, setPassword] = useState<string>("");
    const [username, setUsername] = useState("");

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [isInitialLoading, setIsInitialLoading] = useState<boolean>(() => {
            return !sessionStorage.getItem('visited_auth'); 
    });
        
    const regularExpression = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$/;
    const navigate = useNavigate();
    useEffect(() => {
        if (isInitialLoading) {
            const timer = setTimeout(() => {
                setIsInitialLoading(false);
                // Помечаем, что первый визит прошел
                sessionStorage.setItem('visited_auth', 'true');
            }, 2500);
            return () => clearTimeout(timer);
        }
    }, [isInitialLoading]);
    const handleFormSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        
        // Сбрасываем ошибки перед новой проверкой
        setEmailError(null);
        setPasswordError(null);
        setServerError(null);

        // 1. Сначала валидируем email, и если он не ок — показываем ТОЛЬКО его
        if (!/\S+@\S+\.\S+/.test(email)) {
            setEmailError("Введите корректный email");
            setTimeout(() => setEmailError(null), 3000);
            return;
        }

        // 2. Если email ок — проверяем пароль
        if (!regularExpression.test(password)) {
            setPasswordError("Нужно хотя бы 8 символов, одна буква и цифра");
            setTimeout(() => setPasswordError(null), 3000);
            return;
        }

        
        try {
            if (isSignUp) {
                await AuthenticationServiceService.postAuthSignup({
                username,
                email,
                password,
                });
                setIsLoading(false);
                alert("Регистрация успешна 🎉");
            } else if (isSignIn) {
                await AuthenticationServiceService.postAuthSignin({
                email,
                password,
                });
                setIsLoading(false);
                alert("Вход выполнен 🚀");
            }
        } catch (e: any) {
            setIsLoading(false);
            console.log("Full Error Object:", e);

            // 2. Пытаемся достать код разными путями (зависит от версии кодогенератора)
            const errorCode = e.body?.code || e.code || (typeof e === 'string' ? e : null);
            
            console.log("Extracted Error Code:", errorCode);

            if (!errorCode && !e.body) {
                setIsLoading(false);
                setServerError("Ошибка сети или сервер недоступен");
            } else {
                setIsLoading(false);
                const friendlyMessage = ERROR_MESSAGES[errorCode] || `Ошибка сервера ${errorCode || ""}`;
                setServerError(friendlyMessage);
            }

            if (e.body?.traceId) {
                console.warn("Trace ID:", e.body.traceId);
            }

            setTimeout(() => setServerError(null), 4000);
        } 
    }



    const resetForm = () => {
        setEmail("");
        setPassword("");
        setEmailError(null);
        setPasswordError(null);
    };

    return (
        <div data-theme="dark" className="flex items-center justify-center bg-[#1A1A1A]">
            {isInitialLoading && (
                    <div className="fixed inset-0 z-10000 flex justify-center items-center bg-[#1A1A1A] transition-opacity duration-500">
                        <LoadingPage /> 
                    </div>
                )
            }
            {isLoading && (
                <div className="fixed inset-0 z-10000 flex justify-center items-center bg-[#1A1A1A] transition-opacity duration-500">
                        <LoadingPage />
                </div>
            )}
        <div id="auth-custom-scope">
        <div className="flex justify-center items-center h-screen auth-wrapper">
            <div className="absolute inset-0 bg-cover bg-blue-500/20 blur-[100px] s-64 m-auto rounded-full" />


            {/* Основной контейнер с переключателем классов */}
            <div className={`auth-container ${isSignUp ? "right-panel-active" : ""}`}>
                
                {/* --- ФОРМА РЕГИСТРАЦИИ (Sign Up) --- */}
                <div className="form-container sign-up-container">
                    <form 
                        className="bg-[#222526] flex flex-col items-center justify-center h-full px-12 text-center" 
                        onSubmit={handleFormSubmit}
                        noValidate
                    >
                        <div className="toast toast-top toast-end z-100 flex flex-col gap-2 p-4">
                            {emailError && (
                                <div key="email-err" role="alert" className="alert fade-box shadow-lg">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-[#E0E0E0] h-6 w-6 shrink-0">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                    <span>{emailError}</span>
                                </div>
                            )}
                            {passwordError && (
                                <div key="pass-err" role="alert" className="alert fade-box shadow-lg">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-[#E0E0E0] h-6 w-6 shrink-0">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                    <span>{passwordError}</span>
                                </div>
                            )}
                            {serverError && (
                                <div key="pass-err" role="alert" className="alert fade-box shadow-lg">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-[#E0E0E0] h-6 w-6 shrink-0">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                    <span>{serverError}</span>
                                </div>
                            )}
                        </div>
                        <h1 className="font-bold text-2xl mb-6 text-[#E0E0E0]">Создать аккаунт</h1>
                        
                        {/* Имя */}
                        <div className="relative w-6/12 mb-5">
                            <input
                                type="text"
                                placeholder="Имя"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="input input-ghost w-full bg-[#353A3E] shadow-xl/25 rounded-xl pr-10"
                            />
                            {username && (
                                <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[#BFBFBF]">
                                    <User className="h-4 w-4" />
                                </span>
                            )}
                        </div>

                        {/* Email */}
                        <div className="relative w-6/12 mb-5">
                            <input 
                                type="email" 
                                placeholder="Email" 
                                autoComplete="username"
                                className="input input-ghost w-full bg-[#353A3E] shadow-xl/25 rounded-xl pr-10" 
                                value={email}
                                onChange={(e) => {
                                    setEmail(e.target.value);
                                    if (emailError) setEmailError(null);
                                }}
                                required
                            />
                            {email && (
                                <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[#BFBFBF]">
                                    <Mail className="h-4 w-4" />
                                </span>
                            )}
                        </div>

                        {/* Пароль */}
                        <div className="relative w-6/12 mb-10">
                            <input
                                type="password"
                                placeholder="Пароль"
                                autoComplete="new-password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="input input-ghost w-full bg-[#353A3E] shadow-xl/25 rounded-xl pr-10"
                            />
                            {password && (
                                <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[#BFBFBF]">
                                    <Lock className="h-4 w-4" />
                                </span>
                            )}
                        </div>

                        <button className="btn rounded-full bg-[#222526]/0 text-[#E0E0E0] border border-[#E0E0E0] hover:bg-[#222526] px-12 uppercase tracking-wider font-bold text-xs shadow-xl/15">
                            Регистрация
                        </button>

                    </form>
                </div>

                {/* --- ФОРМА ВХОДА (Sign In) --- */}
                <div className="form-container sign-in-container">
                    <form 
                        className="bg-[#222526] flex flex-col items-center justify-center h-full px-12 text-center"
                        onSubmit={handleFormSubmit}
                        noValidate
                    >
                        <div className="toast toast-top toast-start z-100 flex flex-col gap-2 p-4">
                            {emailError && (
                                <div key="email-err" role="alert" className="alert fade-box-1 shadow-lg">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-[#E0E0E0] h-6 w-6 shrink-0">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                    <span>{emailError}</span>
                                </div>
                            )}
                            {passwordError && (
                                <div key="pass-err" role="alert" className="alert fade-box-1 shadow-lg">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-[#E0E0E0] h-6 w-6 shrink-0">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                    <span>{passwordError}</span>
                                </div>
                            )}
                            {serverError && (
                                <div key="pass-err" role="alert" className="alert fade-box-1 shadow-lg">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-[#E0E0E0] h-6 w-6 shrink-0">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                    <span>{serverError}</span>
                                </div>
                            )}
                        </div>
                        <h1 className="font-bold text-2xl mb-6 text-base-content">Войти</h1>
                        
                        {/* Email */}
                        <div className="relative w-6/12 mb-5">
                            <input 
                                type="email" 
                                placeholder="Email" 
                                autoComplete="username"
                                className="input input-ghost w-full bg-[#353A3E] shadow-xl/25 rounded-xl pr-10" 
                                value={email}
                                onChange={(e) => {
                                    setEmail(e.target.value);
                                    if (emailError) setEmailError(null);
                                }}
                                required
                            />
                            {email && (
                                <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[#BFBFBF]">
                                    <Mail className="h-4 w-4" />
                                </span>
                            )}
                        </div>

                        {/* Пароль */}
                        <div className="relative w-6/12 mb-10">
                            <input
                                type="password"
                                placeholder="Пароль"
                                autoComplete="current-password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="input input-ghost w-full bg-[#353A3E] shadow-xl/25 rounded-xl pr-10"
                            />
                            {password && (
                                <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[#BFBFBF]">
                                    <Lock className="h-4 w-4" />
                                </span>
                            )}
                        </div>
                        
                        <a href="#" className="text-xs text-base-content/70 my-4 hover:text-[#BFBFBF]">Забыли пароль?</a>
                        
                        <button className="btn rounded-full bg-[#222526]/0 text-[#E0E0E0] border-white hover:bg-[#222526] px-12 uppercase tracking-wider shadow-xl/25 font-bold text-xs">
                            Войти
                        </button>
                    </form>
                </div>

                {/* --- ОВЕРЛЕЙ (Шторка) --- */}
                <div className="overlay-container">
                    <div className="overlay">
                        <div className="overlay-panel overlay-left">
                            <Logo className="toast toast-start toast-top w-30 h-30 " />
                            <h1 className="font-bold text-2xl mb-4 text-[#E0E0E0]">С возвращением!</h1>
                            <p className="text-sm font-light leading-5 mb-8 text-[#E0E0E0]">
                                Чтобы оставаться на связи с нами, пожалуйста, войдите
                            </p>
                            <button 
                                className="btn btn-outline rounded-full text-[#E0E0E0] border-white hover:bg-white hover:text-[#1A1A1A] px-12 uppercase tracking-wider font-bold text-xs" 
                                onClick={() => {
                                    setIsSignUp(false);
                                    setIsSignIn(true);
                                    resetForm();
                                }}
                            >
                                Войти
                            </button>
                        </div>
                        <div className="overlay-panel overlay-right">
                            <Logo className="toast toast-end toast-top w-30 h-30 " />
                            <h1 className="font-bold text-2xl mb-4 text-[#E0E0E0]">Привет, друг!</h1>
                            <p className="text-sm font-light leading-5 mb-8 text-[#E0E0E0]">
                                Введите свои данные и начните путешествие с нами
                            </p>
                            <button 
                                className="btn btn-outline rounded-full text-[#E0E0E0] border-white hover:bg-white hover:text-[#1A1A1A] px-12 uppercase tracking-wider font-bold text-xs" 
                                onClick={() => {
                                    setIsSignUp(true);
                                    setIsSignIn(false);
                                    navigate('/signup');
                                    resetForm();
                                }}
                            >
                                Регистрация
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        </div>
        </div>
    );
};

export default AuthForm;