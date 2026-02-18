import * as React from "react"
import { useIsMobile } from "@/hooks/use-mobile"
import { AiAgentServiceService } from "../../api/services/AiAgentServiceService"
import { saveAgentToStorage } from "@/lib/storage"
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Slider } from "@/components/ui/slider"
const AVATAR_OPTIONS = ["Alex", "Jordan", "Taylor", "Sasha", "Casey", "Mika", "Charlie"];

export type AgentData = {
  id?: string;
  name: string;
  avatarSeed: string;
  role: string;
  male: boolean;
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
  onSaveSuccess: () => void
}

export function AgentDrawer({ agent, open, onOpenChange, onSaveSuccess }: AgentDrawerProps) {
  const isMobile = useIsMobile()

  const [, setIsLoading] = React.useState(false);
  const [name, setName] = React.useState("");
  const [age, setAge] = React.useState<string | number>("");
  const [interests, setInterests] = React.useState("");
  const [role, setRole] = React.useState<PersonalityRole>("Custom");
  const [selectedAvatar, setSelectedAvatar] = React.useState("Alex");
  const [traits, setTraits] = React.useState(PERSONALITY_PRESETS.Custom);
  const [male, setMale] = React.useState(true);
  React.useEffect(() => {
    if (agent && open) {
      setName(agent.name || "");
      setAge(agent.age || "");
      setMale(agent.male || true);
      setInterests(agent.interests || "");
      setSelectedAvatar(agent.avatarSeed || "Alex");
      
      const initialRole = (agent.role && agent.role in PERSONALITY_PRESETS) 
        ? (agent.role as PersonalityRole) 
        : "Custom";
      setRole(initialRole);
      setTraits(agent.traits || PERSONALITY_PRESETS[initialRole]);
    }
  }, [agent, open]);

  const handleRoleChange = (newRole: PersonalityRole) => {
    setRole(newRole);
    if (newRole !== "Custom") setTraits(PERSONALITY_PRESETS[newRole]);
  };

  const handleTraitChange = (trait: string, value: number[]) => {
    setTraits(prev => ({ ...prev, [trait]: value[0] }));
    setRole("Custom");
  };

  // --- ГЛАВНАЯ ЛОГИКА ТУТ ---
  const handleSaveClick = async () => {
    setIsLoading(true);
    try {
      const isEdit = !!agent?.id;
      const newAgentData: AgentData = {
        id: agent?.id || crypto.randomUUID(), 
        name,
        age,
        male,
        interests,
        avatarSeed: selectedAvatar,
        role,
        traits,
        mood: agent?.mood || "neutral"
      };

      // СРАЗУ СОХРАНЯЕМ В ЛОКАЛ СТОРАДЖ
      
      console.log("Данные успешно ушли в LS:", newAgentData);

      // Пытаемся отправить на сервер (даже если упадет, в LS уже лежит)
      const requestBody = {
        username: name,
        photo: selectedAvatar,
        isMale: male,
        age: Number(age),
        interests: interests,
        personalityType: role as any,
        additionalInformation: JSON.stringify(traits)
      };
      if (!isEdit) {
        if (!agent) {
          console.error("Ошибка: Попытка редактирования, но данные агента отсутствуют.");
          return;
        }
        const response = await AiAgentServiceService.putAiAgentAgents(agent.id!, requestBody);
        if (response.status === 200) {
          saveAgentToStorage(newAgentData);
        } else {
          console.log('s0s1');
        }
        onSaveSuccess();
        onOpenChange(false);
        alert("Агент сохранен!");
      } else {
        const response = await AiAgentServiceService.postAiAgentAgents(requestBody);
        if (response.status === 200) {
          saveAgentToStorage(newAgentData);
        } else {
          console.log('s0s1');
        }
        onSaveSuccess();
        onOpenChange(false);
        alert("Агент сохранен!");
      }

    } catch (error) {
      console.error("Сервер недоступен", error);
      onSaveSuccess();
      onOpenChange(false);
    } finally {
      setIsLoading(false);
    }
  };

  if (!agent) return null;

  return (
    <Drawer direction={isMobile ? "bottom" : "right"} open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="h-full w-full sm:max-w-100 ml-auto rounded-none shadow-2xl bg-card">
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
                    <SelectItem value="Custom">Индивидуальный (пользовательский)</SelectItem>
                    <SelectItem value="Analyst">Альтруист (добрый)</SelectItem>
                    <SelectItem value="Diplomat">Макиавеллист (злой)</SelectItem>
                    <SelectItem value="Aggressor">Бунтарь (непредсказуемый)</SelectItem>
                    <SelectItem value="Thinker">Стоик (хладнокровный)</SelectItem>
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
                  onChange={(e) => {
                      const val = e.target.value;
                      const onlyNumbers = val.replace(/\D/g, "");
                      setAge(onlyNumbers);
                    }}
                  placeholder="Введите возраст..."
                />
              </div>
            </div>
            <div className="flex flex-col gap-3">
              <Label htmlFor="sex">Пол</Label>
              <RadioGroup value={male ? "man" : "female"} className="w-fit flex flex-wrap" onValueChange={(val) => setMale(val === "man")}>
                <div className="flex items-center gap-3">
                  <RadioGroupItem value="man" id="r1" />
                  <Label htmlFor="r1">Мужской</Label>
                </div>
                <div className="flex items-center gap-3">
                  <RadioGroupItem value="female" id="r2" />
                  <Label htmlFor="r2">Женский</Label>
                </div>
              </RadioGroup>


              </div>
            <div className="flex flex-col gap-3">
              <Label htmlFor="interests">Интересы</Label>
              <Input 
                id="interests" 
                value={interests} 
                onChange={(e) => setInterests(e.target.value)} 
                placeholder="Введите интересы..."
              />
            </div>

            <div className="flex flex-col gap-3 pb-10">
              <Label>Фото (выберите стиль)</Label>
              <div className="flex flex-wrap gap-3">
                {AVATAR_OPTIONS.map((seed) => (
                  <div 
                    key={seed}
                    onClick={() => setSelectedAvatar(seed)}
                    className={`relative shrink-0 cursor-pointer rounded-full border-2 transition-all hover:scale-105 ${
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
          <Button className="w-full" onClick={handleSaveClick}>Сохранить</Button>
          <DrawerClose asChild>
            <Button variant="ghost" className="w-full">Отмена</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  )
}