import * as React from "react"
import { useLocation } from "react-router-dom"
import {
  IconCamera,
  IconBlocks,
  IconDatabase,
  IconFileAi,
  IconFileDescription,
  IconFileWord,
  IconReport,
  IconUsers,
} from "@tabler/icons-react"
import Logo from "./Logo.tsx"
import { NavMain } from "@/components/nav-main"
import { NavSecondary } from "@/components/nav-secondary"
import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  useSidebar,
} from "@/components/ui/sidebar"

const data = {
  user: {
    name: "shadcn",
    email: "m@example.com",
    avatar: "/avatars/shadcn.jpg",
  },
  navMain: [
    {
      title: "Agents",
      url: "/",
      icon: IconUsers,
    },
    {
      title: "Relations",
      url: "/users",
      icon: IconBlocks,
    },
  ],
  navClouds: [
    {
      title: "Capture",
      icon: IconCamera,
      isActive: true,
      url: "#",
      items: [
        {
          title: "Active Proposals",
          url: "#",
        },
        {
          title: "Archived",
          url: "#",
        },
      ],
    },
    {
      title: "Proposal",
      icon: IconFileDescription,
      url: "#",
      items: [
        {
          title: "Active Proposals",
          url: "#",
        },
        {
          title: "Archived",
          url: "#",
        },
      ],
    },
    {
      title: "Prompts",
      icon: IconFileAi,
      url: "#",
      items: [
        {
          title: "Active Proposals",
          url: "#",
        },
        {
          title: "Archived",
          url: "#",
        },
      ],
    },
  ],
  navSecondary: [
  ],
  documents: [
    {
      name: "Data Library",
      url: "#",
      icon: IconDatabase,
    },
    {
      name: "Reports",
      url: "#",
      icon: IconReport,
    },
    {
      name: "Word Assistant",
      url: "#",
      icon: IconFileWord,
    },
  ],
}

import { ChevronRight } from "lucide-react"

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { open, setOpen } = useSidebar()
  const location = useLocation()
  const isUsersPage = location.pathname === "/users"
  if (isUsersPage) {
  return (
  <>
        {/* 1. ТРИГГЕР-СТРЕЛКА (видна всегда, когда сайдбар закрыт) */}
        {!open && (
          <div 
            onMouseEnter={() => setOpen(true)}
            className="fixed left-0 top-1/2 -translate-y-1/2 z-60 flex items-center justify-center w-8 h-24 bg-card border border-l-0 border-border rounded-r-xl cursor-pointer hover:bg-accent transition-colors shadow-md"
          >
            <ChevronRight className="h-4 w-4 text-primary animate-pulse" />
          </div>
        )}

        {/* 2. САЙДБАР */}
        <div 
          onMouseLeave={() => setOpen(false)}
          className={`fixed inset-y-0 left-0 z-50 transition-transform duration-300 ease-in-out ${
            open ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <Sidebar 
            collapsible="none" 
            className="w-65 h-full border-r border-border shadow-2xl"
            {...props}
          >
            <SidebarHeader className="border-b p-0 gap-0">
              <a href="#" className="flex items-center p-0">
              <Logo className="w-20 h-20 shrink-0 -ml-2" />
              <span className="text-base font-semibold -ml-2">MindColony</span>
              </a>
            </SidebarHeader>
            
            <SidebarContent>
              <NavMain items={data.navMain} />
              <NavSecondary items={data.navSecondary} className="mt-auto" />
            </SidebarContent>

            <SidebarFooter className="border-t">
              <NavUser user={data.user} />
            </SidebarFooter>
          </Sidebar>
        </div>
      </>
    )
  }
  return (
    <div className="h-screen border-r border-border bg-card">
      <Sidebar 
        collapsible="offcanvas" 
        className="w-65 h-full"
        {...props}
      >
        <SidebarHeader className="border-b p-0! gap-0">
          <a href="#" className="flex items-center p-0!">
            <Logo className="w-20 h-20 shrink-0 -ml-2" />
            <span className="text-base font-semibold -ml-2">MindColony</span>
          </a>
        </SidebarHeader>
        
        <SidebarContent>
          <NavMain items={data.navMain} />
          <NavSecondary items={data.navSecondary} className="mt-auto" />
        </SidebarContent>

        <SidebarFooter className="border-t">
          <NavUser user={data.user} />
        </SidebarFooter>
      </Sidebar>
    </div>
  )
}
