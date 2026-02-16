import React, { useState } from 'react';
import './AuthForm.css';
import { DefaultService } from "../../api/services/DefaultService";
import Logo from './Logo.tsx'

const AuthForm: React.FC = () => {
    // Типизируем стейт как boolean
    const [isSignUp, setIsSignUp] = useState<boolean>(false);
    const [isSignIn, setIsSignIn] = useState<boolean>(false);
    const [passwordError, setPasswordError] = useState<string | null>(null);
    const [emailError, setEmailError] = useState<string | null>(null);
    const [serverError, setServerError] = useState<string | null>(null);
    const [email, setEmail] = useState<string>("");
    const [password, setPassword] = useState<string>("");
    const [username, setUsername] = useState("");
    
    const regularExpression = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$/;

    const handleFormSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        
        // Сбрасываем старые, чтобы анимация входа проигралась заново
        setEmailError(null);
        setPasswordError(null);
        setServerError(null);
        
        let hasError = false;

            // Проверка почты
        if (!/\S+@\S+\.\S+/.test(email)) {
                setEmailError("Введите корректный email");
                hasError = true;
                setTimeout(() => setEmailError(null), 3000);
        }

        if (!regularExpression.test(password)) {
                setTimeout(() => {
                    setPasswordError("Пароль должен быть минимум 8 символов");
                    setTimeout(() => setPasswordError(null), 3000);
                }, 100); 
                hasError = true;
        }

        if (hasError) return;
        
        try {
            if (isSignUp) {
                await DefaultService.postSignup({
                username,
                email,
                password,
                });

                alert("Регистрация успешна 🎉");
            } else if (isSignIn) {
                await DefaultService.postSignin({
                email,
                password,
                });

                alert("Вход выполнен 🚀");
            }
        } catch (e: any) {
            const err = e.body;

            if (!err) {
                setServerError("Ошибка сети");
                return;
            }

            setServerError(err.message);
            }
    };

    const resetForm = () => {
        setEmail("");
        setPassword("");
        setEmailError(null);
        setPasswordError(null);
    };
    return (
        <div className="flex justify-center items-center h-screen auth-wrapper">
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
                        
                        <input type="text" placeholder="Имя" value={username} onChange={(e) => setUsername(e.target.value)} className="input input-ghost w-6/12 bg-[#353A3E] shadow-xl/25 rounded-xl mb-5" />
                        <input 
                            type="email" 
                            placeholder="Email" 
                            className={`input input-ghost w-6/12 bg-[#353A3E] shadow-xl/25 rounded-xl mb-5`} 
                            value={email}
                            onChange={(e) => {
                                setEmail(e.target.value);
                                if(emailError) setEmailError(null);
                            }}
                            required
                        />
                        <input type="password" placeholder="Пароль" value={password} onChange={(e) => setPassword(e.target.value)}className="input input-ghost w-6/12 bg-[#353A3E] shadow-xl/25 rounded-xl mb-10" />

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
                        
                        <input 
                            type="email" 
                            placeholder="Email" 
                            className={`input input-ghost w-6/12 bg-[#353A3E] shadow-xl/25 rounded-xl mb-5`} 
                            value={email}
                            onChange={(e) => {
                                setEmail(e.target.value);
                                if(emailError) setEmailError(null);
                            }}
                            required
                        />
                        <input type="password" placeholder="Пароль" value={password} onChange={(e) => setPassword(e.target.value)}className="input input-ghost w-6/12 bg-[#353A3E] shadow-xl/25 rounded-xl mb-10" />
                        
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
    );
};

export default AuthForm;