"use client";

import React, { useEffect, useRef, useState } from 'react';
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d';
import { useAgentStream, type AgentLink, type AgentNode } from '@/lib/agent-stream/AgentStreamContext';

interface AgentGraphProps {
  onNodeSelect?: (node: AgentNode) => void;
}

const AgentGraph: React.FC<AgentGraphProps> = ({ onNodeSelect }) => {
  const graphRef = useRef<ForceGraphMethods<AgentNode, AgentLink>>(undefined);
  const { graph: data, selectedAgentId, hoveredAgentId, setSelectedAgentId, setHoveredAgentId, lastPulse } = useAgentStream();
  const [isMounted, setIsMounted] = useState(false);

  // Функция "выстрела" сообщением
  const emitMessage = (sourceId: string, targetId: string) => {
    if (!graphRef.current) return;
    
    const link = data.links.find(l => {
      const sId = typeof l.source === 'object' ? (l.source as any).id : l.source;
      const tId = typeof l.target === 'object' ? (l.target as any).id : l.target;
      return sId === sourceId && tId === targetId;
    });

    if (link) {
      // Ставим временный текст для визуала
      link.message = link.message || "DATA PACKET";
      graphRef.current.emitParticle(link);
      
      // Стираем текст через 2 секунды, чтобы не засирать экран
      setTimeout(() => { link.message = ""; }, 2000);
    }
  };

  // Mounted guard for ForceGraph (canvas) in SSR-like setups
  useEffect(() => setIsMounted(true), []);

  // Pulse particles on real incoming events
  useEffect(() => {
    if (!lastPulse) return;
    emitMessage(lastPulse.sourceId, lastPulse.targetId);
  }, [lastPulse]);

  // Авто-зум
  useEffect(() => {
    if (graphRef.current && data.nodes.length > 0) {
      setTimeout(() => {
        graphRef.current?.zoomToFit(400, 100);
      }, 500);
    }
  }, [data]);

  // Загрузка аватаров
  useEffect(() => {
    data.nodes.forEach(node => {
      if (!node.img) {
        const img = new Image();
        img.src = `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(node.avatarSeed || node.name)}`;
        img.onload = () => { node.img = img; };
      }
    });
  }, [data.nodes]);

  const drawNode = (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const isSelected = selectedAgentId === node.id;
    const isHovered = hoveredAgentId === node.id;
    const size = isSelected ? 8 : isHovered ? 7 : 6;
    const { x, y, name, img } = node;
    
    // Тело узла
    ctx.beginPath();
    ctx.arc(x, y, size, 0, 2 * Math.PI, false);
    ctx.fillStyle = isSelected ? '#a78bfa' : isHovered ? '#818cf8' : '#6366f1';
    ctx.fill();
    ctx.strokeStyle = isSelected ? '#ffffff' : 'rgba(255,255,255,0.75)';
    ctx.lineWidth = (isSelected ? 2.4 : 1.5) / globalScale;
    ctx.stroke();

    // Аватар
    if (img && img.complete) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(x, y, size - 0.5, 0, 2 * Math.PI, false);
      ctx.clip();
      ctx.drawImage(img, x - size, y - size, size * 2, size * 2);
      ctx.restore();
    }

    // Текст имени
    let fontSize = Math.max(10 / globalScale, 4);
    ctx.font = `${fontSize}px Inter, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const opacity = globalScale < 0.2 ? 0 : Math.min(1, (globalScale - 0.2) * 2);
    ctx.fillStyle = `rgba(224, 224, 224, ${opacity})`;

    if (opacity > 0) {
      ctx.fillText(name, x, y + size + 2);
    }
  };

  const drawLinkCanvasObject = (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = link.message;
    if (!label || globalScale < 1.2) return;

    const start = link.source;
    const end = link.target;
    if (typeof start !== 'object' || typeof end !== 'object') return;

    // Вычисляем угол и центр
    const fontSize = 14 / globalScale;
    const relLink = { x: end.x - start.x, y: end.y - start.y };
    let textAngle = Math.atan2(relLink.y, relLink.x);
    if (textAngle > Math.PI / 2) textAngle = -(Math.PI - textAngle);
    if (textAngle < -Math.PI / 2) textAngle = -(-Math.PI - textAngle);

    ctx.save();
    // Переносим контекст в центр ребра
    ctx.translate(start.x + relLink.x / 2, start.y + relLink.y / 2);
    ctx.rotate(textAngle);

    ctx.font = `${fontSize}px monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillStyle = '#818cf8';
    
    // Рисуем текст в 0,0 (так как мы уже сделали translate)
    ctx.fillText(label, 0, -2);
    ctx.restore();
  };

  if (!isMounted) return null;

  return (
    <div className="w-full h-full min-h-150 rounded-xl overflow-hidde relative">
      <ForceGraph2D
        ref={graphRef}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        nodeCanvasObject={drawNode}
        linkCanvasObject={drawLinkCanvasObject}
        linkCanvasObjectMode={() => 'after'}
        
        // Физика
        d3AlphaDecay={0.03}
        d3VelocityDecay={0.3}
        cooldownTicks={100}
        
        // Связи и частицы
        linkColor={(l) => {
          const sId = typeof l.source === "object" ? (l.source as any).id : l.source;
          const tId = typeof l.target === "object" ? (l.target as any).id : l.target;
          if (selectedAgentId && (sId === selectedAgentId || tId === selectedAgentId)) return "rgba(167, 139, 250, 0.55)";
          if (hoveredAgentId && (sId === hoveredAgentId || tId === hoveredAgentId)) return "rgba(129, 140, 248, 0.45)";
          return "rgba(156, 163, 175, 0.2)";
        }}
        linkDirectionalParticles={0} // 0 по дефолту, только emitMessage их создает
        linkDirectionalParticleWidth={2.5}
        linkDirectionalParticleSpeed={0.01}
        linkDirectionalParticleColor={() => "#818cf8"}

        onNodeHover={(node) => setHoveredAgentId(node ? (node as any).id : null)}
        onNodeClick={(node) => {
          const n = node as AgentNode;
          setSelectedAgentId(n?.id ?? null);
          onNodeSelect?.(n);
        }}
      />
    </div>
  );
};

export default AgentGraph;