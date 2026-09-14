with Ada.Text_IO;
with Branch;
with Countdown;

procedure Control_Flow_Test is
   use type Branch.Number;
   use type Countdown.Number;
   Magnitude : Branch.Magnitude;
   Count : Countdown.Number;
begin
   for Input in Branch.Number loop
      Branch.Absolute_Value (Input, Magnitude);
      if Magnitude /= abs Input then
         raise Program_Error with "Wrong branch result";
      end if;
   end loop;
   for Amount in Countdown.Number loop
      Countdown.Count_Down (Amount, Count);
      if Count /= 0 then
         raise Program_Error with "Countdown did not reach zero";
      end if;
   end loop;
   Ada.Text_IO.Put_Line ("PASS: branch 21 inputs; countdown 11 inputs (0, 1, many iterations)");
end Control_Flow_Test;
