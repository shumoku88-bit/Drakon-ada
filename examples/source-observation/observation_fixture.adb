procedure Observation_Fixture
  (Amount : in Integer;
   Result : out Integer)
with SPARK_Mode => On
is
   Remaining : Integer := Amount;
begin
   Result := 0;

   if Remaining < 0 then
      Result := -Remaining;
   else
      while Remaining > 0 loop
         Result := Result + 1;
         Remaining := Remaining - 1;
      end loop;
   end if;

   if Result = 0 then
      return;
   end if;

   Result := Result + 10;
end Observation_Fixture;
