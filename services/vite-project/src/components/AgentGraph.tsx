import * as React from "react"
import { useIsMobile } from "@/hooks/use-mobile"
import { AiAgentServiceService } from "../../api/services/AiAgentServiceService"
import { getAgentsFromStorage, saveAgentToStorage } from "@/lib/storage"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Check, AlertCircle } from "lucide-react"
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
  traits: {
    openness: number;
    conscientiousness: number;
    extraversion: number;
    agreeableness: number;
    neuroticism: number;
  };
  isSynced?: boolean;
  mood?: string;
  ownerId?: string;
}

const PERSONALITY_PRESETS = {
  Analyst: { openness: 80, conscientiousness: 90, extraversion: 40, agreeableness: 50, neuroticism: 30 },
  Diplomat: { openness: 70, conscientiousness: 60, extraversion: 70, agreeableness: 90, neuroticism: 40 },
  Aggressor: { openness: 50, conscientiousness: 70, extraversion: 80, agreeableness: 20, neuroticism: 60 },
  Thinker: { openness: 95, conscientiousness: 40, extraversion: 20, agreeableness: 40, neuroticism: 50 },
  Custom: { openness: 50, conscientiousness: 50, extraversion: 50, agreeableness: 50, neuroticism: 50 },
};

type PersonalityRole = keyof typeof PERSONALITY_PRESETS;

const UI_ROLE_TO_API_ENUM: Record<string, string> = {
  "Custom": "INDIVIDUAL",
  "Analyst": "ALTRUIST",
  "Diplomat": "MACHIAVELLIAN",
  "Aggressor": "REBEL",
  "Thinker": "STOIC"
};

type AgentDrawerProps = {
  agent: AgentData | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaveSuccess: () => void
}

export function AgentDrawer({ agent, open, onOpenChange, onSaveSuccess }: AgentDrawerProps) {
  const isMobile = useIsMobile()

  const [isLoading, setIsLoading] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);

  const [name, setName] = React.useState("");
  const [age, setAge] = React.useState<string | number>("");
  const [interests, setInterests] = React.useState("");
  const [role, setRole] = React.useState<PersonalityRole>("Custom");
  const [selectedAvatar, setSelectedAvatar] = React.useState("Alex");
  const [traits, setTraits] = React.useState(PERSONALITY_PRESETS.Custom);
  const [male, setMale] = React.useState(true);

  // ← ЛОГИРОВАНИЕ: Отслеживаем получение agent
  React.useEffect(() => {
    if (open) {
      setServerError(null);
      console.log("📦 AgentDrawer opened with agent:", agent);
      console.log("📦 agent?.isSynced value:", agent?.isSynced);

      if (agent) {
        setName(agent.name || "");
        setAge(agent.age || "");
        setMale(agent.male ?? true);
        setInterests(agent.interests || "");
        setSelectedAvatar(agent.avatarSeed || "Alex");

        const mappedRole = agent.role && agent.role in PERSONALITY_PRESETS
          ? (agent.role as PersonalityRole)
          : "Custom";

        setRole(mappedRole);
        setTraits(agent.traits || PERSONALITY_PRESETS[mappedRole]);
      } else {
        setName("");
        setAge("");
        setMale(true);
        setInterests("");
        setSelectedAvatar("Alex");
        setRole("Custom");
        setTraits(PERSONALITY_PRESETS.Custom);
      }
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

  const handleSaveClick = async () => {
    setIsLoading(true);
    setServerError(null);

    // ← ЛОГИРОВАНИЕ: Начало сохранения
    console.log("💾 handleSaveClick started");
    console.log("💾 agent object:", agent);
    console.log("💾 agent?.isSynced:", agent?.isSynced);
    console.log("💾 agent?.id:", agent?.id);

    try {
      const userId = localStorage.getItem("userId");
      console.log("💾 userId from localStorage:", userId);

      // ← ЛОГИРОВАНИЕ: Проверка isEdit
      const isEdit = agent?.isSynced === true;
      console.log("💾 isEdit calculated as:", isEdit);
      console.log("💾 agent?.isSynced === true evaluates to:", agent?.isSynced === true);

      if (!userId && !isEdit) {
        console.log("❌ No userId and not edit - blocking save");
        setServerError("Пользователь не авторизован (отсутствует userId).");
        setIsLoading(false);
        return;
      }

      const newAgentData: AgentData = {
        id: agent?.id || crypto.randomUUID(),
        name,
        age,
        male,
        interests,
        avatarSeed: selectedAvatar,
        role,
        traits,
        mood: agent?.mood || "neutral",
        isSynced: true
      };

      console.log("💾 newAgentData to save:", newAgentData);

      const requestBody: any = {
        userId: userId,
        username: name,
        photoLink: selectedAvatar,
        isMale: male,
        age: Number(age),
        interests,
        personalityType: UI_ROLE_TO_API_ENUM[role] ?? "INDIVIDUAL",
        traits: traits,
        additionalInformation: ""
      };

      // ← ЛОГИРОВАНИЕ: Выбор метода запроса
      if (isEdit) {
        console.log("✏️ EXECUTING PUT REQUEST (edit mode)");
        console.log("✏️ PUT URL: /ai-agent/agents/", agent!.id);
        await AiAgentServiceService.putAiAgentAgents(agent!.id!, requestBody);
        console.log("✏️ PUT request completed successfully");
      } else {
        console.log("➕ EXECUTING POST REQUEST (create mode)");
        const response = await AiAgentServiceService.postAiAgentAgents(requestBody);
        console.log("➕ POST request completed, response:", response);
        if (response?.id) {
          newAgentData.id = response.id;
          console.log("➕ Updated newAgentData.id with server response:", response.id);
        }
      }

      console.log("💾 Saving to localStorage...");
      saveAgentToStorage(newAgentData);
      console.log("💾 Save to localStorage completed");

      onSaveSuccess();
      onOpenChange(false);
    } catch (err: any) {
      console.error("❌ Error during save:", err);
      console.error("❌ Error response:", err?.response);
      console.error("❌ Error data:", err?.response?.data);
      const message = err?.response?.data?.message || err?.message || "Не удалось сохранить агента";
      setServerError(message);
    } finally {
      setIsLoading(false);
      console.log("💾 handleSaveClick finished");
    }
  };

  return (
    <Drawer direction={isMobile ? "bottom" : "right"} open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="h-full w-full sm:max-w-100 ml-auto rounded-none shadow-2xl bg-card">
        <DrawerHeader className="gap-1">
          <DrawerTitle>{agent?.isSynced ? "Редактирование" : "Новый агент"}</DrawerTitle>
          <DrawerDescription>Настройка параметров ИИ-агента</DrawerDescription>
        </DrawerHeader>

        {serverError && (
          <div className="mx-4 mb-2 rounded-md border border-red-500 bg-red-50 p-3 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 mt-0.5" />
              <div>
                <p className="font-medium text-sm">Ошибка</p>
                <p className="text-sm opacity-90">{serverError}</p>
              </div>
            </div>
          </div>
        )}

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
                disabled={isLoading}
              />
            </div>

            <div className="grid gap-2">
              <div className="flex flex-col gap-3">
                <Label htmlFor="type">Личность</Label>
                <Select value={role} onValueChange={handleRoleChange} disabled={isLoading}>
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

              <div className="space-y-6 pt-2 pb-8 touch-none">
                <Label className="text-xs uppercase tracking-widest text-muted-foreground font-bold">
                  Характеристики (OCEAN)
                </Label>

                <div className="space-y-3">
                   <div className="flex justify-between text-xs">
                    <span className="font-medium">O (Openness)</span>
                    <span className="text-primary font-mono">{traits.openness}%</span>
                   </div>
                   <Slider
                    disabled={isLoading}
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
                        disabled={isLoading}
                        value={[traits.conscientiousness]}
                        max={100} step={1}
                        onValueChange={(val) => handleTraitChange('conscientiousness', val)}
                    />
                </div>

                <div className="space-y-3">
                    <div className="flex justify-between text-xs">
                        <span className="font-medium">E (Extraversion) — Экстраверсия</span>
                        <span className="text-primary font-mono">{traits.extraversion}%</span>
                    </div>
                    <Slider
                        disabled={isLoading}
                        value={[traits.extraversion]}
                        max={100} step={1}
                        onValueChange={(val) => handleTraitChange('extraversion', val)}
                    />
                </div>

                <div className="space-y-3">
                    <div className="flex justify-between text-xs">
                        <span className="font-medium">A (Agreeableness) — Доброжелательность</span>
                        <span className="text-primary font-mono">{traits.agreeableness}%</span>
                    </div>
                    <Slider
                        disabled={isLoading}
                        value={[traits.agreeableness]}
                        max={100} step={1}
                        onValueChange={(val) => handleTraitChange('agreeableness', val)}
                    />
                </div>

                <div className="space-y-3">
                    <div className="flex justify-between text-xs">
                        <span className="font-medium">N (Neuroticism) — Невротизм</span>
                        <span className="text-primary font-mono">{traits.neuroticism}%</span>
                    </div>
                    <Slider
                        disabled={isLoading}
                        value={[traits.neuroticism]}
                        max={100} step={1}
                        onValueChange={(val) => handleTraitChange('neuroticism', val)}
                    />
                </div>
              </div>

              <div className="flex flex-col gap-3">
                <Label htmlFor="age">Возраст</Label>
                <Input
                  id="age"
                  value={age}
                  disabled={isLoading}
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
              <RadioGroup
                disabled={isLoading}
                value={male ? "man" : "female"}
                className="w-fit flex flex-wrap"
                onValueChange={(val) => setMale(val === "man")}
              >
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
                disabled={isLoading}
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
                    onClick={() => !isLoading && setSelectedAvatar(seed)}
                    className={`relative shrink-0 cursor-pointer rounded-full border-2 transition-all hover:scale-105 ${
                      selectedAvatar === seed ? "border-primary ring-2 ring-primary/20" : "border-transparent"
                    } ${isLoading ? "opacity-50 cursor-not-allowed" : ""}`}
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
          <Button className="w-full" onClick={handleSaveClick} disabled={isLoading}>
            {isLoading ? "Сохранение..." : "Сохранить"}
          </Button>
          <DrawerClose asChild>
            <Button variant="ghost" className="w-full" disabled={isLoading}>Отмена</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  )
}

export default AgentDrawer;