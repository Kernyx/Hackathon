import * as React from "react"
import { useIsMobile } from "@/hooks/use-mobile"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Check } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer"
import { Slider } from "@/components/ui/slider"

// --- ТИПЫ И КОНСТАНТЫ ---
const AVATAR_OPTIONS = ["Alex", "Jordan", "Taylor", "Sasha", "Casey", "Mika", "Charlie"];

// Типизируем структуру данных агента
export type AgentData = {
  id?: string;
  name: string;
  avatarSeed: string;
  role: string;
  age: string | number;
  interests: string;
  mood?: string;
  traits: {
    openness: number;
    conscientiousness: number;
    extraversion: number;
    agreeableness: number;
    neuroticism: number;
  };
}

const PERSONALITY_PRESETS = {
  Analyst: { openness: 80, conscientiousness: 90, extraversion: 40, agreeableness: 50, neuroticism: 30 },
  Diplomat: { openness: 70, conscientiousness: 60, extraversion: 70, agreeableness: 90, neuroticism: 40 },
  Aggressor: { openness: 50, conscientiousness: 70, extraversion: 80, agreeableness: 20, neuroticism: 60 },
  Thinker: { openness: 95, conscientiousness: 40, extraversion: 20, agreeableness: 40, neuroticism: 50 },
  Custom: { openness: 50, conscientiousness: 50, extraversion: 50, agreeableness: 50, neuroticism: 50 },
};

type PersonalityRole = keyof typeof PERSONALITY_PRESETS;

type AgentDrawerProps = {
  agent: AgentData | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (data: AgentData) => void // <--- Добавили колбек сохранения
}

export function AgentDrawer({ agent, open, onOpenChange, onSave }: AgentDrawerProps) {
  const isMobile = useIsMobile()

  // Стейты для всех полей формы
  const [name, setName] = React.useState("");
  const [age, setAge] = React.useState<string | number>("");
  const [interests, setInterests] = React.useState("");
  const [role, setRole] = React.useState<PersonalityRole>("Custom");
  const [selectedAvatar, setSelectedAvatar] = React.useState("Alex");
  const [traits, setTraits] = React.useState(PERSONALITY_PRESETS.Custom);

  // Эффект: при открытии (или смене агента) заполняем форму данными
  React.useEffect(() => {
    if (agent) {
      setName(agent.name || "");
      setAge(agent.age || "");
      setInterests(agent.interests || "");
      setSelectedAvatar(agent.avatarSeed || agent.name || "Alex");// Или хранить аватар отдельно

      const initialRole = (agent.role && agent.role in PERSONALITY_PRESETS) 
        ? (agent.role as PersonalityRole) 
        : "Custom";
      
      setRole(initialRole);
      
      // Если у агента уже есть черты, берем их, иначе берем из пресета
      if (agent.traits) {
        setTraits(agent.traits);
      } else {
        setTraits(PERSONALITY_PRESETS[initialRole]);
      }
    }
  }, [agent]);

  const handleRoleChange = (newRole: PersonalityRole) => {
    setRole(newRole);
    if (newRole !== "Custom") {
      setTraits(PERSONALITY_PRESETS[newRole]);
    }
  };

  const handleTraitChange = (trait: string, value: number[]) => {
    setTraits(prev => ({ ...prev, [trait]: value[0] }));
    setRole("Custom");
  };

  // Главная функция сохранения
  const handleSaveClick = () => {
    if (!agent) return;

    const newAgentData: AgentData = {
      ...agent, // Сохраняем ID если был
      name,
      avatarSeed: selectedAvatar,
      role,
      age,
      interests,
      traits,
      mood: agent.mood || "neutral", // Дефолтное настроение
    };
    
    // Подменяем имя аватара на выбранное, если логика требует совпадения
    // В данном случае аватар генерируется от имени, но мы использовали seed
    if (selectedAvatar) {
        // Если твоя логика требует, чтобы аватар зависел от selectedAvatar,
        // можно передать его отдельно или использовать как часть имени
    }

    onSave(newAgentData);
    onOpenChange(false); // Закрываем
  };

  if (!agent) return null;

  return (
    <Drawer direction={isMobile ? "bottom" : "right"} open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="h-full w-full sm:max-w-[400px] ml-auto rounded-none border-none shadow-2xl bg-card">
        <DrawerHeader className="gap-1">
          <DrawerTitle>{agent.id ? "Редактирование" : "Новый агент"}</DrawerTitle>
          <DrawerDescription>Настройка параметров ИИ-агента</DrawerDescription>
        </DrawerHeader>
        
        <div className="flex flex-col gap-4 overflow-y-auto px-4 text-sm [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
          {!isMobile && <Separator className="opacity-50" />}
          
          <form className="flex flex-col gap-4" onSubmit={(e) => e.preventDefault()}>
            <div className="flex flex-col gap-3">
              <Label htmlFor="name">Имя агента</Label>
              <Input 
                id="name" 
                value={name} 
                onChange={(e) => setName(e.target.value)} 
                placeholder="Введите имя..."
              />
            </div>

            <div className="grid gap-2">
              <div className="flex flex-col gap-3">
                <Label htmlFor="type">Личность</Label>
                <Select value={role} onValueChange={handleRoleChange}>
                  <SelectTrigger id="type" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Analyst">Аналитик</SelectItem>
                    <SelectItem value="Diplomat">Дипломат</SelectItem>
                    <SelectItem value="Aggressor">Агрессор</SelectItem>
                    <SelectItem value="Thinker">Мыслитель</SelectItem>
                    <SelectItem value="Custom">Пользовательский</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Секция ползунков (без изменений, только используем state traits) */}
              <div className="space-y-6 pt-2 pb-8 touch-none">
                <Label className="text-xs uppercase tracking-widest text-muted-foreground font-bold">
                  Характеристики (OCEAN)
                </Label>
                {/* Пример для O (Openness), остальные аналогично */}
                <div className="space-y-3">
                   <div className="flex justify-between text-xs">
                    <span className="font-medium">O (Openness)</span>
                    <span className="text-primary font-mono">{traits.openness}%</span>
                   </div>
                   <Slider 
                    value={[traits.openness]} max={100} step={1} 
                    onValueChange={(val) => handleTraitChange('openness', val)}
                   />
                </div>
            <div className="space-y-3">

                <div className="flex justify-between text-xs">

                <span className="font-medium">C (Conscientiousness) — Добросовестность</span>

                <span className="text-primary font-mono">{traits.conscientiousness}%</span>

                </div>

                <Slider

                value={[traits.conscientiousness]}

                max={100}

                step={1}

                onValueChange={(val) => handleTraitChange('conscientiousness', val)}

                onPointerDown={(e) => e.stopPropagation()}

                onPointerMove={(e) => e.stopPropagation()}

                onPointerUp={(e) => e.stopPropagation()}

                />

                <p className="text-[10px] text-muted-foreground leading-tight">

                Организованность и дисциплина. Влияет на следование планам.

                </p>

            </div>



            {/* E — Extraversion */}

            <div className="space-y-3">

                <div className="flex justify-between text-xs">

                <span className="font-medium">E (Extraversion) — Экстраверсия</span>

                <span className="text-primary font-mono">{traits.extraversion}%</span>

                </div>

                <Slider

                value={[traits.extraversion]}

                max={100}

                step={1}

                onValueChange={(val) => handleTraitChange('extraversion', val)}

                onPointerDown={(e) => e.stopPropagation()}

                onPointerMove={(e) => e.stopPropagation()}

                onPointerUp={(e) => e.stopPropagation()}

                />

                <p className="text-[10px] text-muted-foreground leading-tight">

                Общительность. Влияет на частоту инициации чатов с другими агентами.

                </p>

            </div>



            {/* A — Agreeableness */}

            <div className="space-y-3">

                <div className="flex justify-between text-xs">

                <span className="font-medium">A (Agreeableness) — Доброжелательность</span>

                <span className="text-primary font-mono">{traits.agreeableness}%</span>

                </div>

                <Slider

                value={[traits.agreeableness]}

                max={100}

                step={1}

                onValueChange={(val) => handleTraitChange('agreeableness', val)}

                onPointerDown={(e) => e.stopPropagation()}

                onPointerMove={(e) => e.stopPropagation()}

                onPointerUp={(e) => e.stopPropagation()}

                />

                <p className="text-[10px] text-muted-foreground leading-tight">

                Склонность к сотрудничеству. Влияет на базовый уровень симпатии к незнакомцам.

                </p>

            </div>



            {/* N — Neuroticism */}

            <div className="space-y-3">

                <div className="flex justify-between text-xs">

                <span className="font-medium">N (Neuroticism) — Невротизм</span>

                <span className="text-primary font-mono">{traits.neuroticism}%</span>

                </div>

                <Slider

                value={[traits.neuroticism]}

                max={100}

                step={1}

                onValueChange={(val) => handleTraitChange('neuroticism', val)}

                onPointerDown={(e) => e.stopPropagation()}

                onPointerMove={(e) => e.stopPropagation()}

                onPointerUp={(e) => e.stopPropagation()}

                />

                <p className="text-[10px] text-muted-foreground leading-tight">

                Эмоциональная нестабильность. Влияет на то, как быстро «портится» настроение.

                </p>

            </div>

                {/* ... Тут твои остальные слайдеры для C, E, A, N ... */}
                {/* Для краткости я их пропустил, но они должны использовать traits из state */}
              </div>

              <div className="flex flex-col gap-3">
                <Label htmlFor="age">Возраст</Label>
                <Input 
                  id="age" 
                  value={age} 
                  onChange={(e) => setAge(e.target.value)} 
                />
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <Label htmlFor="interests">Интересы</Label>
              <Input 
                id="interests" 
                value={interests} 
                onChange={(e) => setInterests(e.target.value)} 
              />
            </div>

            <div className="flex flex-col gap-3 pb-10">
              <Label>Фото (выберите стиль)</Label>
              <div className="flex flex-wrap gap-3">
                {AVATAR_OPTIONS.map((seed) => (
                  <div 
                    key={seed}
                    onClick={() => setSelectedAvatar(seed)}
                    className={`relative flex-shrink-0 cursor-pointer rounded-full border-2 transition-all hover:scale-105 ${
                      selectedAvatar === seed ? "border-primary ring-2 ring-primary/20" : "border-transparent"
                    }`}
                  >
                    <img 
                      src={`https://api.dicebear.com/7.x/notionists/svg?seed=${seed}`} 
                      alt={seed}
                      className="h-12 w-12 rounded-full bg-muted"
                    />
                    {selectedAvatar === seed && (
                      <div className="absolute -right-1 -top-1 rounded-full bg-primary p-0.5 text-primary-foreground">
                        <Check className="h-3 w-3" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </form>
        </div>

        <DrawerFooter className="mt-auto">
          {/* Вешаем обработчик на кнопку */}
          <Button className="w-full" onClick={handleSaveClick}>Сохранить</Button>
          <DrawerClose asChild>
            <Button variant="ghost" className="w-full">Отмена</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  )
}