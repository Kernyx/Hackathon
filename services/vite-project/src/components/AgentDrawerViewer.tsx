import { useIsMobile } from "@/hooks/use-mobile"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer"

export function AgentDrawerViewer({ agent, children }: { agent: any, children: React.ReactNode }) {
  const isMobile = useIsMobile()

  return (
    <Drawer direction={isMobile ? "bottom" : "right"}>
      <DrawerTrigger asChild>
        {children}
      </DrawerTrigger>
      <DrawerContent className={!isMobile ? "h-full w-100 ml-auto rounded-l-xl" : ""}>
        <DrawerHeader className="gap-1">
          <DrawerTitle>{agent.name}</DrawerTitle>
          <DrawerDescription>
            Настройка параметров ИИ-агента
          </DrawerDescription>
        </DrawerHeader>
        <div className="flex flex-col gap-4 overflow-y-auto px-4 text-sm">
          {!isMobile && (
            <>
              <Separator />
              <div className="grid gap-2">
                <div className="flex gap-2 leading-none font-medium">
                  Статус системы: Активен
                </div>
                <div className="text-muted-foreground text-xs">
                  Здесь вы можете изменить базовые директивы агента. 
                  Все изменения вступят в силу немедленно.
                </div>
              </div>
              <Separator />
            </>
          )}
          <form className="flex flex-col gap-4">
            {/* Имя агента */}
            <div className="flex flex-col gap-3">
              <Label htmlFor="name">Имя агента</Label>
              <Input id="name" defaultValue={agent.name} />
            </div>

            <div className="grid grid-cols-1 gap-4">
              <div className="flex flex-col gap-3">
                <Label htmlFor="age">Возраст</Label>
                <Input id="age" type="text" defaultValue={25} />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4">
              <div className="flex flex-col gap-3">
                <Label htmlFor="interests">Интересы</Label>
                <Input id="interests" defaultValue="Coding" />
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <Label htmlFor="extra">Доп. параметры</Label>
              <Input id="extra" defaultValue="Любит тишину" />
            </div>
          </form>
        </div>
        <DrawerFooter>
          <Button>Submit</Button>
          <DrawerClose asChild>
            <Button variant="outline">Done</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  )
}